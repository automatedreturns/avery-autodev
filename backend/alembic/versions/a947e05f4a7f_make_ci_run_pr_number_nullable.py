"""make_ci_run_pr_number_nullable

Revision ID: a947e05f4a7f
Revises: a884662a1703
Create Date: 2026-01-07 17:00:16.497671

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a947e05f4a7f'
down_revision: Union[str, None] = 'a884662a1703'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Make pr_number nullable to support push events (non-PR builds)
    # Use batch mode for SQLite compatibility
    with op.batch_alter_table('ci_runs', schema=None) as batch_op:
        batch_op.alter_column('pr_number',
                              existing_type=sa.Integer(),
                              nullable=True)


def downgrade() -> None:
    # Revert pr_number to not nullable (data loss possible if null values exist)
    with op.batch_alter_table('ci_runs', schema=None) as batch_op:
        batch_op.alter_column('pr_number',
                              existing_type=sa.Integer(),
                              nullable=False)
