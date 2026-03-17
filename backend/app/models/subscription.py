from datetime import datetime, timedelta
from enum import Enum

from sqlalchemy import Column, DateTime, Enum as SQLEnum, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class SubscriptionPlan(str, Enum):
    """Subscription plan types."""
    FREE = "free"
    PRO = "pro"
    TEAM = "team"
    ENTERPRISE = "enterprise"


class SubscriptionStatus(str, Enum):
    """Subscription status types."""
    ACTIVE = "active"
    CANCELED = "canceled"
    PAST_DUE = "past_due"
    INCOMPLETE = "incomplete"
    TRIALING = "trialing"


class Subscription(Base):
    """Subscription model for managing user billing and quotas."""

    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)

    # Plan details
    plan = Column(SQLEnum(SubscriptionPlan), default=SubscriptionPlan.FREE, nullable=False)
    status = Column(SQLEnum(SubscriptionStatus), default=SubscriptionStatus.ACTIVE, nullable=False)

    # Stripe integration
    stripe_customer_id = Column(String, unique=True, nullable=True, index=True)
    stripe_subscription_id = Column(String, unique=True, nullable=True, index=True)

    # Billing period
    current_period_start = Column(DateTime, default=datetime.utcnow, nullable=False)
    current_period_end = Column(DateTime, nullable=False)

    # Quotas (monthly limits)
    agent_execution_quota = Column(Integer, default=3, nullable=False)   # Free tier default
    test_generation_quota = Column(Integer, default=5, nullable=False)   # Free tier default

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    canceled_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="subscription")
    usage_records = relationship("UsageRecord", back_populates="subscription", cascade="all, delete-orphan")
    overage_purchases = relationship("OveragePurchase", back_populates="subscription", cascade="all, delete-orphan")

    def __init__(self, **kwargs):
        """Initialize subscription with default period if not provided."""
        super().__init__(**kwargs)
        if not self.current_period_end:
            self.current_period_end = self.current_period_start + timedelta(days=30)

    @property
    def is_active(self) -> bool:
        """Check if subscription is currently active."""
        return self.status == SubscriptionStatus.ACTIVE

    @property
    def is_paid_plan(self) -> bool:
        """Check if this is a paid subscription."""
        return self.plan in [SubscriptionPlan.PRO, SubscriptionPlan.TEAM, SubscriptionPlan.ENTERPRISE]

    @property
    def days_until_renewal(self) -> int:
        """Calculate days until billing period renewal."""
        if not self.current_period_end:
            return 0
        delta = self.current_period_end - datetime.utcnow()
        return max(0, delta.days)


class EventType(str, Enum):
    """Usage event types for tracking."""
    AGENT_EXECUTION = "agent_execution"
    TEST_GENERATION = "test_generation"
    CHAT_MESSAGE = "chat_message"  # Future: may meter chat messages


class UsageRecord(Base):
    """Usage record for tracking billable events."""

    __tablename__ = "usage_records"

    id = Column(Integer, primary_key=True, index=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id", ondelete="CASCADE"), nullable=False, index=True)

    # Event details
    event_type = Column(SQLEnum(EventType), nullable=False, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True)
    resource_id = Column(String, nullable=True)  # e.g., task_id, test_suite_id

    # Billing tracking
    cost_credits = Column(Integer, default=1, nullable=False)  # Number of credits consumed
    billing_period_start = Column(DateTime, nullable=False, index=True)  # For aggregation queries

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    event_metadata = Column(String, nullable=True)  # JSON string for additional context

    # Relationships
    subscription = relationship("Subscription", back_populates="usage_records")
    workspace = relationship("Workspace")


class OveragePurchase(Base):
    """Overage purchase record for additional credits."""

    __tablename__ = "overage_purchases"

    id = Column(Integer, primary_key=True, index=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id", ondelete="CASCADE"), nullable=False)

    # Purchase details
    event_type = Column(SQLEnum(EventType), nullable=False)
    quantity = Column(Integer, nullable=False)  # Number of credits purchased
    amount_paid_cents = Column(Integer, nullable=False)  # Amount in cents (e.g., 75 = $0.75)

    # Stripe integration
    stripe_payment_intent_id = Column(String, unique=True, nullable=True, index=True)
    stripe_charge_id = Column(String, nullable=True)

    # Status
    status = Column(String, default="pending", nullable=False)  # pending, completed, failed, refunded

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    subscription = relationship("Subscription", back_populates="overage_purchases")

    @property
    def amount_dollars(self) -> float:
        """Get amount in dollars."""
        return self.amount_paid_cents / 100.0
