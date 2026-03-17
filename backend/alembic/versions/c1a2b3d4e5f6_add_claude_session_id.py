"""add_claude_session_id

Revision ID: c1a2b3d4e5f6
Revises: b8f3d9e5c2a1
Create Date: 2026-01-20 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'c1a2b3d4e5f6'
down_revision: Union[str, None] = '6933a7af410f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    # Add claude_session_id field to workspace_tasks table for SDK session continuation
    if not column_exists('workspace_tasks', 'claude_session_id'):
        op.add_column('workspace_tasks', sa.Column('claude_session_id', sa.String(), nullable=True))


def downgrade() -> None:
    # Remove claude_session_id field from workspace_tasks table
    if column_exists('workspace_tasks', 'claude_session_id'):
        op.drop_column('workspace_tasks', 'claude_session_id')
