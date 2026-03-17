"""add_attachment_processing_fields

Revision ID: a7ce50bd6a4a
Revises: d8d9a387a8a1
Create Date: 2025-12-19 11:23:29.348454

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'a7ce50bd6a4a'
down_revision: Union[str, None] = 'd8d9a387a8a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    # Add attachment processing fields to workspace_tasks table if they don't exist
    if not column_exists('workspace_tasks', 'attachments_metadata'):
        op.add_column('workspace_tasks', sa.Column('attachments_metadata', sa.Text(), nullable=True))

    if not column_exists('workspace_tasks', 'attachments_processed_at'):
        op.add_column('workspace_tasks', sa.Column('attachments_processed_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    # Remove attachment processing fields from workspace_tasks table if they exist
    if column_exists('workspace_tasks', 'attachments_processed_at'):
        op.drop_column('workspace_tasks', 'attachments_processed_at')

    if column_exists('workspace_tasks', 'attachments_metadata'):
        op.drop_column('workspace_tasks', 'attachments_metadata')
