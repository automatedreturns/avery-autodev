"""add_subscription_models

Revision ID: 67bb1fdbf2ba
Revises: 56b788844df9
Create Date: 2025-12-17 12:52:45.012778

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '67bb1fdbf2ba'
down_revision: Union[str, None] = '56b788844df9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def table_exists(table_name: str) -> bool:
    """Check if a table exists."""
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def index_exists(index_name: str, table_name: str) -> bool:
    """Check if an index exists on a table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    try:
        indexes = inspector.get_indexes(table_name)
        return any(idx['name'] == index_name for idx in indexes)
    except:
        return False


def upgrade() -> None:
    # Create subscriptions table
    if not table_exists('subscriptions'):
        op.create_table(
            'subscriptions',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('plan', sa.Enum('FREE', 'PRO', 'TEAM', 'ENTERPRISE', name='subscriptionplan'), nullable=False),
            sa.Column('status', sa.Enum('ACTIVE', 'CANCELED', 'PAST_DUE', 'INCOMPLETE', 'TRIALING', name='subscriptionstatus'), nullable=False),
            sa.Column('stripe_customer_id', sa.String(), nullable=True),
            sa.Column('stripe_subscription_id', sa.String(), nullable=True),
            sa.Column('current_period_start', sa.DateTime(), nullable=False),
            sa.Column('current_period_end', sa.DateTime(), nullable=False),
            sa.Column('agent_execution_quota', sa.Integer(), nullable=False),
            sa.Column('test_generation_quota', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.Column('canceled_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_id'),
            sa.UniqueConstraint('stripe_customer_id'),
            sa.UniqueConstraint('stripe_subscription_id')
        )

    # Create indexes for subscriptions table
    if table_exists('subscriptions'):
        if not index_exists('ix_subscriptions_id', 'subscriptions'):
            op.create_index(op.f('ix_subscriptions_id'), 'subscriptions', ['id'], unique=False)
        if not index_exists('ix_subscriptions_stripe_customer_id', 'subscriptions'):
            op.create_index(op.f('ix_subscriptions_stripe_customer_id'), 'subscriptions', ['stripe_customer_id'], unique=False)
        if not index_exists('ix_subscriptions_stripe_subscription_id', 'subscriptions'):
            op.create_index(op.f('ix_subscriptions_stripe_subscription_id'), 'subscriptions', ['stripe_subscription_id'], unique=False)

    # Create usage_records table
    if not table_exists('usage_records'):
        op.create_table(
            'usage_records',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('subscription_id', sa.Integer(), nullable=False),
            sa.Column('event_type', sa.Enum('AGENT_EXECUTION', 'TEST_GENERATION', 'CHAT_MESSAGE', name='eventtype'), nullable=False),
            sa.Column('workspace_id', sa.Integer(), nullable=True),
            sa.Column('resource_id', sa.String(), nullable=True),
            sa.Column('cost_credits', sa.Integer(), nullable=False),
            sa.Column('billing_period_start', sa.DateTime(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('event_metadata', sa.String(), nullable=True),
            sa.ForeignKeyConstraint(['subscription_id'], ['subscriptions.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id')
        )

    # Create indexes for usage_records table
    if table_exists('usage_records'):
        if not index_exists('ix_usage_records_billing_period_start', 'usage_records'):
            op.create_index(op.f('ix_usage_records_billing_period_start'), 'usage_records', ['billing_period_start'], unique=False)
        if not index_exists('ix_usage_records_created_at', 'usage_records'):
            op.create_index(op.f('ix_usage_records_created_at'), 'usage_records', ['created_at'], unique=False)
        if not index_exists('ix_usage_records_event_type', 'usage_records'):
            op.create_index(op.f('ix_usage_records_event_type'), 'usage_records', ['event_type'], unique=False)
        if not index_exists('ix_usage_records_id', 'usage_records'):
            op.create_index(op.f('ix_usage_records_id'), 'usage_records', ['id'], unique=False)
        if not index_exists('ix_usage_records_subscription_id', 'usage_records'):
            op.create_index(op.f('ix_usage_records_subscription_id'), 'usage_records', ['subscription_id'], unique=False)

    # Create overage_purchases table
    if not table_exists('overage_purchases'):
        op.create_table(
            'overage_purchases',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('subscription_id', sa.Integer(), nullable=False),
            sa.Column('event_type', sa.Enum('AGENT_EXECUTION', 'TEST_GENERATION', 'CHAT_MESSAGE', name='eventtype'), nullable=False),
            sa.Column('quantity', sa.Integer(), nullable=False),
            sa.Column('amount_paid_cents', sa.Integer(), nullable=False),
            sa.Column('stripe_payment_intent_id', sa.String(), nullable=True),
            sa.Column('stripe_charge_id', sa.String(), nullable=True),
            sa.Column('status', sa.String(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('completed_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['subscription_id'], ['subscriptions.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('stripe_payment_intent_id')
        )

    # Create indexes for overage_purchases table
    if table_exists('overage_purchases'):
        if not index_exists('ix_overage_purchases_id', 'overage_purchases'):
            op.create_index(op.f('ix_overage_purchases_id'), 'overage_purchases', ['id'], unique=False)
        if not index_exists('ix_overage_purchases_stripe_payment_intent_id', 'overage_purchases'):
            op.create_index(op.f('ix_overage_purchases_stripe_payment_intent_id'), 'overage_purchases', ['stripe_payment_intent_id'], unique=False)


def downgrade() -> None:
    # Drop tables in reverse order with existence checks
    if table_exists('overage_purchases'):
        if index_exists('ix_overage_purchases_stripe_payment_intent_id', 'overage_purchases'):
            op.drop_index(op.f('ix_overage_purchases_stripe_payment_intent_id'), table_name='overage_purchases')
        if index_exists('ix_overage_purchases_id', 'overage_purchases'):
            op.drop_index(op.f('ix_overage_purchases_id'), table_name='overage_purchases')
        op.drop_table('overage_purchases')

    if table_exists('usage_records'):
        if index_exists('ix_usage_records_subscription_id', 'usage_records'):
            op.drop_index(op.f('ix_usage_records_subscription_id'), table_name='usage_records')
        if index_exists('ix_usage_records_id', 'usage_records'):
            op.drop_index(op.f('ix_usage_records_id'), table_name='usage_records')
        if index_exists('ix_usage_records_event_type', 'usage_records'):
            op.drop_index(op.f('ix_usage_records_event_type'), table_name='usage_records')
        if index_exists('ix_usage_records_created_at', 'usage_records'):
            op.drop_index(op.f('ix_usage_records_created_at'), table_name='usage_records')
        if index_exists('ix_usage_records_billing_period_start', 'usage_records'):
            op.drop_index(op.f('ix_usage_records_billing_period_start'), table_name='usage_records')
        op.drop_table('usage_records')

    if table_exists('subscriptions'):
        if index_exists('ix_subscriptions_stripe_subscription_id', 'subscriptions'):
            op.drop_index(op.f('ix_subscriptions_stripe_subscription_id'), table_name='subscriptions')
        if index_exists('ix_subscriptions_stripe_customer_id', 'subscriptions'):
            op.drop_index(op.f('ix_subscriptions_stripe_customer_id'), table_name='subscriptions')
        if index_exists('ix_subscriptions_id', 'subscriptions'):
            op.drop_index(op.f('ix_subscriptions_id'), table_name='subscriptions')
        op.drop_table('subscriptions')
