"""Pydantic schemas for subscription management."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.subscription import EventType, SubscriptionPlan, SubscriptionStatus


# Subscription Schemas
class SubscriptionBase(BaseModel):
    """Base subscription schema."""

    plan: SubscriptionPlan
    status: SubscriptionStatus


class SubscriptionCreate(SubscriptionBase):
    """Schema for creating a subscription."""

    user_id: int


class SubscriptionUpdate(BaseModel):
    """Schema for updating a subscription."""

    plan: Optional[SubscriptionPlan] = None
    status: Optional[SubscriptionStatus] = None
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None


class SubscriptionResponse(SubscriptionBase):
    """Schema for subscription response."""

    id: int
    user_id: int
    stripe_customer_id: Optional[str]
    stripe_subscription_id: Optional[str]
    current_period_start: datetime
    current_period_end: datetime
    agent_execution_quota: int
    test_generation_quota: int
    created_at: datetime
    updated_at: Optional[datetime]
    canceled_at: Optional[datetime]

    class Config:
        from_attributes = True


# Usage Record Schemas
class UsageRecordCreate(BaseModel):
    """Schema for creating a usage record."""

    event_type: EventType
    workspace_id: Optional[int] = None
    resource_id: Optional[str] = None
    event_metadata: Optional[str] = None


class UsageRecordResponse(BaseModel):
    """Schema for usage record response."""

    id: int
    subscription_id: int
    event_type: EventType
    workspace_id: Optional[int]
    resource_id: Optional[str]
    cost_credits: int
    billing_period_start: datetime
    created_at: datetime
    event_metadata: Optional[str]

    class Config:
        from_attributes = True


# Overage Purchase Schemas
class OveragePurchaseCreate(BaseModel):
    """Schema for creating an overage purchase."""

    event_type: EventType
    quantity: int = Field(gt=0, description="Number of credits to purchase")


class OveragePurchaseResponse(BaseModel):
    """Schema for overage purchase response."""

    id: int
    subscription_id: int
    event_type: EventType
    quantity: int
    amount_paid_cents: int
    stripe_payment_intent_id: Optional[str]
    stripe_charge_id: Optional[str]
    status: str
    created_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


# Quota Check Schemas
class QuotaCheckResponse(BaseModel):
    """Schema for quota check response."""

    allowed: bool
    remaining: int
    quota: int
    used: int
    overage_credits: int = 0
    requires_upgrade: bool
    can_purchase_overage: bool
    overage_price_cents: int
    plan: str
    status: str


# Usage Summary Schemas
class UsageSummaryResponse(BaseModel):
    """Schema for usage summary response."""

    subscription: dict
    quotas: dict
    usage: dict
    remaining: dict


# Stripe Checkout Schemas
class CheckoutSessionCreate(BaseModel):
    """Schema for creating a Stripe checkout session."""

    plan: SubscriptionPlan = Field(
        description="Subscription plan to subscribe to (PRO, TEAM, or ENTERPRISE)"
    )


class CheckoutSessionResponse(BaseModel):
    """Schema for checkout session response."""

    checkout_url: str
    session_id: str


# Stripe Webhook Schemas
class StripeWebhookEvent(BaseModel):
    """Schema for Stripe webhook event."""

    type: str
    data: dict


# Overage Payment Intent Schemas
class OveragePaymentIntentCreate(BaseModel):
    """Schema for creating an overage payment intent."""

    event_type: EventType
    quantity: int = Field(gt=0, le=100, description="Number of credits (1-100)")


class OveragePaymentIntentResponse(BaseModel):
    """Schema for overage payment intent response."""

    client_secret: str
    amount_cents: int
    quantity: int
    event_type: str
