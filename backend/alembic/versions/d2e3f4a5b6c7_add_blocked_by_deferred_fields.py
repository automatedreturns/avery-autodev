"""add_blocked_by_deferred_fields

Revision ID: d2e3f4a5b6c7
Revises: c1a2b3d4e5f6
Create Date: 2026-02-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'd2e3f4a5b6c7'
down_revision: Union[str, None] = 'c1a2b3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    # Add deferred/blocked-by fields to polling_status
    if not column_exists('polling_status', 'last_poll_issues_deferred'):
        op.add_column('polling_status',
            sa.Column('last_poll_issues_deferred', sa.Integer(),
                       nullable=False, server_default='0'))

    if not column_exists('polling_status', 'last_poll_deferred_issue_numbers'):
        op.add_column('polling_status',
            sa.Column('last_poll_deferred_issue_numbers', sa.Text(),
                       nullable=True))

    # Add deferred/blocked-by fields to polling_history
    if not column_exists('polling_history', 'issues_deferred'):
        op.add_column('polling_history',
            sa.Column('issues_deferred', sa.Integer(),
                       nullable=False, server_default='0'))

    if not column_exists('polling_history', 'deferred_issue_numbers'):
        op.add_column('polling_history',
            sa.Column('deferred_issue_numbers', sa.Text(),
                       nullable=True))


def downgrade() -> None:
    if column_exists('polling_history', 'deferred_issue_numbers'):
        op.drop_column('polling_history', 'deferred_issue_numbers')
    if column_exists('polling_history', 'issues_deferred'):
        op.drop_column('polling_history', 'issues_deferred')
    if column_exists('polling_status', 'last_poll_deferred_issue_numbers'):
        op.drop_column('polling_status', 'last_poll_deferred_issue_numbers')
    if column_exists('polling_status', 'last_poll_issues_deferred'):
        op.drop_column('polling_status', 'last_poll_issues_deferred')
