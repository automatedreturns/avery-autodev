"""Subscription management API endpoints."""
from typing import Optional

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.core.config import settings
from app.models.subscription import EventType, SubscriptionPlan
from app.models.user import User
from app.schemas.subscription import (
    CheckoutSessionCreate,
    CheckoutSessionResponse,
    OveragePaymentIntentCreate,
    OveragePaymentIntentResponse,
    QuotaCheckResponse,
    SubscriptionResponse,
    UsageSummaryResponse,
)
from app.services.subscription_service import SubscriptionService

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


@router.get("/me", response_model=SubscriptionResponse)
async def get_my_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current user's subscription details."""
    subscription = SubscriptionService.get_or_create_subscription(db, current_user.id)
    return subscription


@router.get("/usage", response_model=UsageSummaryResponse)
async def get_usage_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get usage summary for current billing period."""
    return SubscriptionService.get_usage_summary(db, current_user.id)


@router.get("/quota-check", response_model=QuotaCheckResponse)
async def check_quota(
    type: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Check if user has quota remaining for event type.

    Args:
        type: Event type (agent_execution or test_generation)
    """
    # Validate and convert event type
    type_upper = type.upper()
    valid_types = {
        "AGENT_EXECUTION": EventType.AGENT_EXECUTION,
        "TEST_GENERATION": EventType.TEST_GENERATION,
    }

    if type_upper not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid event type: {type}. Must be 'agent_execution' or 'test_generation'"
        )

    event_type = valid_types[type_upper]
    return SubscriptionService.check_quota(db, current_user.id, event_type)


@router.post("/checkout", response_model=CheckoutSessionResponse)
async def create_checkout_session(
    data: CheckoutSessionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create Stripe checkout session for subscription upgrade.

    Creates a Stripe hosted checkout page for the user to complete payment.
    """
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=503,
            detail="Stripe is not configured. Please contact support."
        )

    subscription = SubscriptionService.get_or_create_subscription(db, current_user.id)

    # Don't allow downgrade via this endpoint
    if subscription.plan != SubscriptionPlan.FREE and data.plan != SubscriptionPlan.ENTERPRISE:
        raise HTTPException(
            status_code=400,
            detail="You can only upgrade to a higher plan. To downgrade, cancel your subscription."
        )

    # Create or get Stripe customer
    if not subscription.stripe_customer_id:
        try:
            customer = stripe.Customer.create(
                email=current_user.email,
                name=current_user.username,
                metadata={"user_id": current_user.id},
            )
            subscription.stripe_customer_id = customer.id
            db.commit()
        except stripe.error.StripeError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create Stripe customer: {str(e)}"
            )

    # Get price ID based on plan
    if data.plan == SubscriptionPlan.PRO:
        price_id = settings.STRIPE_PRO_PRICE_ID
    elif data.plan == SubscriptionPlan.TEAM:
        price_id = settings.STRIPE_TEAM_PRICE_ID
    else:
        raise HTTPException(
            status_code=400,
            detail="Invalid plan. Must be PRO or TEAM."
        )

    if not price_id:
        raise HTTPException(
            status_code=503,
            detail=f"Stripe price for {data.plan} is not configured. Please contact support."
        )

    # Create checkout session
    try:
        checkout_session = stripe.checkout.Session.create(
            customer=subscription.stripe_customer_id,
            mode="subscription",
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=f"{settings.FRONTEND_URL}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{settings.FRONTEND_URL}/pricing",
            metadata={
                "user_id": current_user.id,
                "plan": data.plan.value,
            },
            allow_promotion_codes=True,  # Allow users to enter promo codes
        )
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create checkout session: {str(e)}"
        )

    return CheckoutSessionResponse(
        checkout_url=checkout_session.url,
        session_id=checkout_session.id,
    )


@router.post("/cancel")
async def cancel_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Cancel user's subscription.

    Subscription remains active until the end of the current billing period,
    then automatically downgrades to free tier.
    """
    subscription = SubscriptionService.get_or_create_subscription(db, current_user.id)

    if subscription.plan == SubscriptionPlan.FREE:
        raise HTTPException(
            status_code=400,
            detail="You are already on the free plan."
        )

    if not subscription.stripe_subscription_id:
        # No Stripe subscription, just downgrade immediately
        SubscriptionService.cancel_subscription(db, current_user.id)
        return {
            "message": "Subscription canceled successfully.",
            "effective_date": "immediately"
        }

    # Cancel Stripe subscription at period end
    try:
        stripe_sub = stripe.Subscription.modify(
            subscription.stripe_subscription_id,
            cancel_at_period_end=True
        )

        # Update our database
        SubscriptionService.cancel_subscription(db, current_user.id)

        return {
            "message": "Subscription will be canceled at the end of your billing period.",
            "effective_date": subscription.current_period_end.isoformat(),
            "days_remaining": subscription.days_until_renewal
        }
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to cancel subscription: {str(e)}"
        )


@router.post("/purchase-overage", response_model=OveragePaymentIntentResponse)
async def purchase_overage(
    data: OveragePaymentIntentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a payment intent for purchasing additional credits (overage).

    Returns a client_secret that the frontend uses with Stripe.js to complete payment.
    """
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=503,
            detail="Stripe is not configured. Please contact support."
        )

    subscription = SubscriptionService.get_or_create_subscription(db, current_user.id)

    # Only paid plans can purchase overage
    if subscription.plan == SubscriptionPlan.FREE:
        raise HTTPException(
            status_code=403,
            detail="Overage purchases are only available for Pro, Team, and Enterprise plans. Please upgrade first."
        )

    # Calculate amount
    price_per_unit = SubscriptionService.OVERAGE_PRICING.get(data.event_type, 0)
    if price_per_unit == 0:
        raise HTTPException(
            status_code=400,
            detail=f"Overage pricing not configured for {data.event_type}"
        )

    amount_cents = price_per_unit * data.quantity

    # Create payment intent
    try:
        payment_intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency="usd",
            customer=subscription.stripe_customer_id,
            metadata={
                "user_id": current_user.id,
                "event_type": data.event_type.value,
                "quantity": data.quantity,
            },
            description=f"Avery - {data.quantity}x {data.event_type.value.replace('_', ' ').title()} credits",
        )

        # Record the pending purchase
        SubscriptionService.create_overage_purchase(
            db,
            user_id=current_user.id,
            event_type=data.event_type,
            quantity=data.quantity,
            amount_paid_cents=amount_cents,
            stripe_payment_intent_id=payment_intent.id,
        )

        return OveragePaymentIntentResponse(
            client_secret=payment_intent.client_secret,
            amount_cents=amount_cents,
            quantity=data.quantity,
            event_type=data.event_type.value,
        )
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create payment intent: {str(e)}"
        )


@router.post("/webhook", include_in_schema=False)
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Handle Stripe webhook events.

    This endpoint receives events from Stripe when payments succeed, subscriptions
    are updated, etc. Must be registered in Stripe Dashboard.
    """
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=503,
            detail="Stripe webhook secret not configured"
        )

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Handle different event types
    event_type = event.type
    event_data = event.data.object

    try:
        if event_type == "checkout.session.completed":
            # User completed checkout, upgrade their subscription
            session = event_data
            user_id = int(session.metadata.get("user_id"))
            plan_str = session.metadata.get("plan")

            try:
                plan = SubscriptionPlan(plan_str)
            except ValueError:
                print(f"Invalid plan in webhook: {plan_str}")
                return {"status": "error", "message": "Invalid plan"}

            # Get the Stripe subscription ID
            stripe_subscription_id = session.subscription

            # Upgrade the user
            SubscriptionService.upgrade_subscription(
                db, user_id, plan, stripe_subscription_id
            )
            print(f"Upgraded user {user_id} to {plan}")

        elif event_type == "customer.subscription.updated":
            # Subscription was updated (e.g., renewed, changed)
            stripe_sub = event_data
            # You can sync subscription details here if needed
            pass

        elif event_type == "customer.subscription.deleted":
            # Subscription was canceled and has now ended
            stripe_sub = event_data
            # Find subscription by stripe_subscription_id and downgrade to free
            from app.models.subscription import Subscription

            subscription = db.query(Subscription).filter(
                Subscription.stripe_subscription_id == stripe_sub.id
            ).first()

            if subscription:
                # Downgrade to free
                SubscriptionService.upgrade_subscription(
                    db, subscription.user_id, SubscriptionPlan.FREE, None
                )
                print(f"Downgraded user {subscription.user_id} to FREE after subscription ended")

        elif event_type == "payment_intent.succeeded":
            # Payment for overage succeeded
            payment_intent = event_data
            user_id = int(payment_intent.metadata.get("user_id", 0))

            if user_id:
                # Find the overage purchase and mark as completed
                from app.models.subscription import OveragePurchase

                purchase = db.query(OveragePurchase).filter(
                    OveragePurchase.stripe_payment_intent_id == payment_intent.id
                ).first()

                if purchase:
                    SubscriptionService.complete_overage_purchase(
                        db, purchase.id, payment_intent.charges.data[0].id if payment_intent.charges.data else None
                    )
                    print(f"Completed overage purchase {purchase.id} for user {user_id}")

        elif event_type == "payment_intent.payment_failed":
            # Payment failed
            payment_intent = event_data
            # You could send an email notification here
            print(f"Payment failed for PaymentIntent {payment_intent.id}")

    except Exception as e:
        print(f"Error processing webhook {event_type}: {str(e)}")
        # Don't raise exception - return 200 to Stripe to avoid retries
        return {"status": "error", "message": str(e)}

    return {"status": "success"}
