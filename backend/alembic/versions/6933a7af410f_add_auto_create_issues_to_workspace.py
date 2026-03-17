"""add_auto_create_issues_to_workspace

Revision ID: 6933a7af410f
Revises: a947e05f4a7f
Create Date: 2026-01-07 19:34:31.125081

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6933a7af410f'
down_revision: Union[str, None] = 'a947e05f4a7f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add auto_create_issues column to workspaces table
    op.add_column('workspaces', sa.Column('auto_create_issues', sa.Boolean(), nullable=False, server_default='true'))


def downgrade() -> None:
    # Remove auto_create_issues column from workspaces table
    op.drop_column('workspaces', 'auto_create_issues')
