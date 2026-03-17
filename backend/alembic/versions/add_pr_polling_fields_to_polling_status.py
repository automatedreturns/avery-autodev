"""add_pr_polling_fields_to_polling_status

Revision ID: b9e8c7d5f3a2
Revises: a7ce50bd6a4a
Create Date: 2025-12-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'b9e8c7d5f3a2'
down_revision: Union[str, None] = 'a7ce50bd6a4a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    # Add PR polling fields to polling_status table if they don't exist
    if not column_exists('polling_status', 'last_poll_prs_checked'):
        op.add_column('polling_status', sa.Column('last_poll_prs_checked', sa.Integer(), nullable=False, server_default='0'))

    if not column_exists('polling_status', 'last_poll_prs_with_conflicts'):
        op.add_column('polling_status', sa.Column('last_poll_prs_with_conflicts', sa.Integer(), nullable=False, server_default='0'))

    if not column_exists('polling_status', 'total_pr_tasks_created'):
        op.add_column('polling_status', sa.Column('total_pr_tasks_created', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    # Remove PR polling fields from polling_status table if they exist
    if column_exists('polling_status', 'total_pr_tasks_created'):
        op.drop_column('polling_status', 'total_pr_tasks_created')

    if column_exists('polling_status', 'last_poll_prs_with_conflicts'):
        op.drop_column('polling_status', 'last_poll_prs_with_conflicts')

    if column_exists('polling_status', 'last_poll_prs_checked'):
        op.drop_column('polling_status', 'last_poll_prs_checked')
