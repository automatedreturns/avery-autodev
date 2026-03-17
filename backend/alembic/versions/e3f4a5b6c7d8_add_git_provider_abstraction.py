"""add git provider abstraction fields

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-03-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'e3f4a5b6c7d8'
down_revision: Union[str, None] = 'd2e3f4a5b6c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column already exists in a table."""
    bind = op.get_bind()
    insp = inspect(bind)
    columns = [col["name"] for col in insp.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    # Add GitLab fields to users table
    if not _column_exists("users", "gitlab_token_encrypted"):
        op.add_column("users", sa.Column("gitlab_token_encrypted", sa.String(), nullable=True))
    if not _column_exists("users", "gitlab_username"):
        op.add_column("users", sa.Column("gitlab_username", sa.String(), nullable=True))
    if not _column_exists("users", "gitlab_url"):
        op.add_column("users", sa.Column("gitlab_url", sa.String(), nullable=True))

    # Add git_provider and gitlab_url fields to workspaces table
    if not _column_exists("workspaces", "git_provider"):
        op.add_column(
            "workspaces",
            sa.Column("git_provider", sa.String(), nullable=False, server_default="github"),
        )
    if not _column_exists("workspaces", "gitlab_url"):
        op.add_column("workspaces", sa.Column("gitlab_url", sa.String(), nullable=True))


def downgrade() -> None:
    # Remove workspace fields
    if _column_exists("workspaces", "gitlab_url"):
        op.drop_column("workspaces", "gitlab_url")
    if _column_exists("workspaces", "git_provider"):
        op.drop_column("workspaces", "git_provider")

    # Remove user fields
    if _column_exists("users", "gitlab_url"):
        op.drop_column("users", "gitlab_url")
    if _column_exists("users", "gitlab_username"):
        op.drop_column("users", "gitlab_username")
    if _column_exists("users", "gitlab_token_encrypted"):
        op.drop_column("users", "gitlab_token_encrypted")
