"""merge_heads

Revision ID: d8d9a387a8a1
Revises: 67bb1fdbf2ba, add_agent_jobs_001
Create Date: 2025-12-19 11:23:23.798104

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8d9a387a8a1'
down_revision: Union[str, None] = ('67bb1fdbf2ba', 'add_agent_jobs_001')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
