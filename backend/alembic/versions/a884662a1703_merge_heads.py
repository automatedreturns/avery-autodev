"""merge_heads

Revision ID: a884662a1703
Revises: b9e8c7d5f3a2, b8f3d9e5c2a1
Create Date: 2026-01-07 17:00:09.227790

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a884662a1703'
down_revision: Union[str, None] = ('b9e8c7d5f3a2', 'b8f3d9e5c2a1')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
