"""Service for managing subscriptions, quotas, and usage tracking."""
from datetime import datetime, timedelta
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.subscription import (
    EventType,
    OveragePurchase,
    Subscription,
    SubscriptionPlan,
    SubscriptionStatus,
    UsageRecord,
)
from app.models.user import User


class SubscriptionService:
    """Service for subscription and quota management."""

    # Default quotas for each plan
    PLAN_QUOTAS = {
        SubscriptionPlan.FREE: {
            "agent_execution_quota": 3,
            "test_generation_quota": 5,
        },
        SubscriptionPlan.PRO: {
            "agent_execution_quota": 25,
            "test_generation_quota": 50,
        },
        SubscriptionPlan.TEAM: {
            "agent_execution_quota": 100,
            "test_generation_quota": 200,
        },
        SubscriptionPlan.ENTERPRISE: {
            "agent_execution_quota": 999999,  # "Unlimited" with fair use
            "test_generation_quota": 999999,
        },
    }

    # Overage pricing (in cents)
    OVERAGE_PRICING = {
        EventType.AGENT_EXECUTION: 400,  # $4.00 for Pro (can be tiered by plan if needed)
        EventType.TEST_GENERATION: 50,   # $0.50
    }

    # Plan-specific overage pricing (optional - for different rates per plan)
    PLAN_OVERAGE_PRICING = {
        SubscriptionPlan.PRO: {
            EventType.AGENT_EXECUTION: 400,  # $4.00
            EventType.TEST_GENERATION: 50,   # $0.50
        },
        SubscriptionPlan.TEAM: {
            EventType.AGENT_EXECUTION: 300,  # $3.00
            EventType.TEST_GENERATION: 50,   # $0.50
        },
    }

    @staticmethod
    def get_or_create_subscription(db: Session, user_id: int) -> Subscription:
        """
        Get user's subscription or create a subscription.
        Internal users (@goodgist.com) get Team plan, others get Free plan.

        Args:
            db: Database session
            user_id: User ID

        Returns:
            Subscription object
        """
        subscription = db.query(Subscription).filter(Subscription.user_id == user_id).first()

        if not subscription:
            # Get user to check email domain
            user = db.query(User).filter(User.id == user_id).first()

            # Check if user is internal (from configured internal domain)
            is_internal = (
                user and
                user.email and
                user.email.lower().endswith(f'@{settings.INTERNAL_EMAIL_DOMAIN.lower()}')
            )

            # Assign plan based on email domain
            plan = SubscriptionPlan.TEAM if is_internal else SubscriptionPlan.FREE

            # Create subscription with appropriate plan
            now = datetime.utcnow()
            subscription = Subscription(
                user_id=user_id,
                plan=plan,
                status=SubscriptionStatus.ACTIVE,
                current_period_start=now,
                current_period_end=now + timedelta(days=30),
                agent_execution_quota=SubscriptionService.PLAN_QUOTAS[plan][
                    "agent_execution_quota"
                ],
                test_generation_quota=SubscriptionService.PLAN_QUOTAS[plan][
                    "test_generation_quota"
                ],
            )
            db.add(subscription)
            db.commit()
            db.refresh(subscription)

        return subscription

    @staticmethod
    def check_quota(db: Session, user_id: int, event_type: EventType) -> Dict:
        """
        Check if user has quota remaining for the event type.

        Args:
            db: Database session
            user_id: User ID
            event_type: Type of event (AGENT_EXECUTION, TEST_GENERATION)

        Returns:
            Dict with quota information:
            {
                "allowed": bool,
                "remaining": int,
                "quota": int,
                "used": int,
                "requires_upgrade": bool,
                "can_purchase_overage": bool,
                "overage_price_cents": int
            }
        """
        subscription = SubscriptionService.get_or_create_subscription(db, user_id)

        # Get current billing period usage
        period_start = subscription.current_period_start
        period_end = subscription.current_period_end

        # Check if we're in a new billing period
        now = datetime.utcnow()
        if now > period_end:
            # Auto-renew the billing period for active subscriptions
            if subscription.status == SubscriptionStatus.ACTIVE:
                subscription.current_period_start = period_end
                subscription.current_period_end = period_end + timedelta(days=30)
                db.commit()
                period_start = subscription.current_period_start
                period_end = subscription.current_period_end

        # Count usage in current period using date range
        usage_count = (
            db.query(UsageRecord)
            .filter(
                UsageRecord.subscription_id == subscription.id,
                UsageRecord.event_type == event_type,
                UsageRecord.created_at >= period_start,
                UsageRecord.created_at < period_end,
            )
            .count()
        )

        # Count any overage purchases for this period
        overage_credits = (
            db.query(OveragePurchase)
            .filter(
                OveragePurchase.subscription_id == subscription.id,
                OveragePurchase.event_type == event_type,
                OveragePurchase.status == "completed",
                OveragePurchase.created_at >= period_start,
                OveragePurchase.created_at <= period_end,
            )
            .with_entities(db.func.sum(OveragePurchase.quantity))
            .scalar()
            or 0
        )

        # Determine quota based on event type
        if event_type == EventType.AGENT_EXECUTION:
            base_quota = subscription.agent_execution_quota
        elif event_type == EventType.TEST_GENERATION:
            base_quota = subscription.test_generation_quota
        else:
            base_quota = 0

        total_quota = base_quota + overage_credits
        remaining = max(0, total_quota - usage_count)
        allowed = remaining > 0

        return {
            "allowed": allowed,
            "remaining": remaining,
            "quota": base_quota,
            "used": usage_count,
            "overage_credits": overage_credits,
            "requires_upgrade": not allowed and subscription.plan == SubscriptionPlan.FREE,
            "can_purchase_overage": not allowed and subscription.plan != SubscriptionPlan.FREE,
            "overage_price_cents": SubscriptionService.OVERAGE_PRICING.get(event_type, 0),
            "plan": subscription.plan.value,
            "status": subscription.status.value,
        }

    @staticmethod
    def record_usage(
        db: Session,
        user_id: int,
        event_type: EventType,
        workspace_id: Optional[int] = None,
        resource_id: Optional[str] = None,
        metadata: Optional[str] = None,
    ) -> UsageRecord:
        """
        Record a usage event for billing tracking.

        Args:
            db: Database session
            user_id: User ID
            event_type: Type of event
            workspace_id: Optional workspace ID
            resource_id: Optional resource ID (task_id, test_suite_id, etc.)
            metadata: Optional JSON metadata

        Returns:
            Created UsageRecord
        """
        subscription = SubscriptionService.get_or_create_subscription(db, user_id)

        usage = UsageRecord(
            subscription_id=subscription.id,
            event_type=event_type,
            workspace_id=workspace_id,
            resource_id=resource_id,
            billing_period_start=subscription.current_period_start,
            event_metadata=metadata,
        )
        db.add(usage)
        db.commit()
        db.refresh(usage)

        return usage

    @staticmethod
    def get_usage_summary(db: Session, user_id: int) -> Dict:
        """
        Get usage summary for current billing period.

        Args:
            db: Database session
            user_id: User ID

        Returns:
            Dict with usage summary for all event types
        """
        subscription = SubscriptionService.get_or_create_subscription(db, user_id)

        period_start = subscription.current_period_start
        period_end = subscription.current_period_end

        # Check if we're in a new billing period and auto-renew if needed
        now = datetime.utcnow()
        if now > period_end:
            # Auto-renew the billing period for active subscriptions
            if subscription.status == SubscriptionStatus.ACTIVE:
                subscription.current_period_start = period_end
                subscription.current_period_end = period_end + timedelta(days=30)
                db.commit()
                period_start = subscription.current_period_start
                period_end = subscription.current_period_end

        # Count usage by event type using date range
        usage_by_type = {}
        for event_type in [EventType.AGENT_EXECUTION, EventType.TEST_GENERATION]:
            count = (
                db.query(UsageRecord)
                .filter(
                    UsageRecord.subscription_id == subscription.id,
                    UsageRecord.event_type == event_type,
                    UsageRecord.created_at >= period_start,
                    UsageRecord.created_at < period_end,
                )
                .count()
            )
            usage_by_type[event_type.value] = count

        return {
            "subscription": {
                "plan": subscription.plan.value,
                "status": subscription.status.value,
                "current_period_start": subscription.current_period_start.isoformat(),
                "current_period_end": subscription.current_period_end.isoformat(),
                "days_until_renewal": subscription.days_until_renewal,
            },
            "quotas": {
                "agent_execution": subscription.agent_execution_quota,
                "test_generation": subscription.test_generation_quota,
            },
            "usage": {
                "agent_execution": usage_by_type.get(EventType.AGENT_EXECUTION.value, 0),
                "test_generation": usage_by_type.get(EventType.TEST_GENERATION.value, 0),
            },
            "remaining": {
                "agent_execution": max(
                    0,
                    subscription.agent_execution_quota
                    - usage_by_type.get(EventType.AGENT_EXECUTION.value, 0),
                ),
                "test_generation": max(
                    0,
                    subscription.test_generation_quota
                    - usage_by_type.get(EventType.TEST_GENERATION.value, 0),
                ),
            },
        }

    @staticmethod
    def upgrade_subscription(
        db: Session,
        user_id: int,
        new_plan: SubscriptionPlan,
        stripe_subscription_id: Optional[str] = None,
    ) -> Subscription:
        """
        Upgrade user's subscription to a new plan.

        Args:
            db: Database session
            user_id: User ID
            new_plan: New subscription plan
            stripe_subscription_id: Optional Stripe subscription ID

        Returns:
            Updated Subscription object
        """
        subscription = SubscriptionService.get_or_create_subscription(db, user_id)

        # Update plan and quotas
        subscription.plan = new_plan
        subscription.agent_execution_quota = SubscriptionService.PLAN_QUOTAS[new_plan][
            "agent_execution_quota"
        ]
        subscription.test_generation_quota = SubscriptionService.PLAN_QUOTAS[new_plan][
            "test_generation_quota"
        ]

        if stripe_subscription_id:
            subscription.stripe_subscription_id = stripe_subscription_id

        subscription.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(subscription)

        return subscription

    @staticmethod
    def cancel_subscription(db: Session, user_id: int) -> Subscription:
        """
        Cancel user's subscription (downgrade to free at period end).

        Args:
            db: Database session
            user_id: User ID

        Returns:
            Updated Subscription object
        """
        subscription = SubscriptionService.get_or_create_subscription(db, user_id)

        subscription.status = SubscriptionStatus.CANCELED
        subscription.canceled_at = datetime.utcnow()
        subscription.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(subscription)

        return subscription

    @staticmethod
    def create_overage_purchase(
        db: Session,
        user_id: int,
        event_type: EventType,
        quantity: int,
        amount_paid_cents: int,
        stripe_payment_intent_id: Optional[str] = None,
    ) -> OveragePurchase:
        """
        Record an overage credit purchase.

        Args:
            db: Database session
            user_id: User ID
            event_type: Type of event credits are for
            quantity: Number of credits purchased
            amount_paid_cents: Amount paid in cents
            stripe_payment_intent_id: Optional Stripe Payment Intent ID

        Returns:
            Created OveragePurchase object
        """
        subscription = SubscriptionService.get_or_create_subscription(db, user_id)

        purchase = OveragePurchase(
            subscription_id=subscription.id,
            event_type=event_type,
            quantity=quantity,
            amount_paid_cents=amount_paid_cents,
            stripe_payment_intent_id=stripe_payment_intent_id,
            status="pending",
        )
        db.add(purchase)
        db.commit()
        db.refresh(purchase)

        return purchase

    @staticmethod
    def complete_overage_purchase(
        db: Session, purchase_id: int, stripe_charge_id: Optional[str] = None
    ) -> OveragePurchase:
        """
        Mark an overage purchase as completed.

        Args:
            db: Database session
            purchase_id: OveragePurchase ID
            stripe_charge_id: Optional Stripe Charge ID

        Returns:
            Updated OveragePurchase object
        """
        purchase = db.query(OveragePurchase).filter(OveragePurchase.id == purchase_id).first()

        if not purchase:
            raise ValueError(f"OveragePurchase with id {purchase_id} not found")

        purchase.status = "completed"
        purchase.completed_at = datetime.utcnow()

        if stripe_charge_id:
            purchase.stripe_charge_id = stripe_charge_id

        db.commit()
        db.refresh(purchase)

        return purchase
