"""add_policy_integration_fields

Revision ID: b8f3d9e5c2a1
Revises: a7ce50bd6a4a
Create Date: 2026-01-06 18:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'b8f3d9e5c2a1'
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
    # Add policy integration fields to ci_runs table
    if not column_exists('ci_runs', 'coverage_snapshot_id'):
        op.add_column('ci_runs', sa.Column('coverage_snapshot_id', sa.Integer(), nullable=True))

    if not column_exists('ci_runs', 'policy_passed'):
        op.add_column('ci_runs', sa.Column('policy_passed', sa.Boolean(), nullable=True))

    if not column_exists('ci_runs', 'policy_violations'):
        op.add_column('ci_runs', sa.Column('policy_violations', sa.JSON(), nullable=True))

    # Add policy integration fields to workspace_tasks table
    if not column_exists('workspace_tasks', 'pre_pr_policy_check'):
        op.add_column('workspace_tasks', sa.Column('pre_pr_policy_check', sa.JSON(), nullable=True))

    if not column_exists('workspace_tasks', 'coverage_snapshot_id'):
        op.add_column('workspace_tasks', sa.Column('coverage_snapshot_id', sa.Integer(), nullable=True))

    # Create foreign key constraints if tables exist
    # Skip for SQLite as it requires batch mode for FK constraints
    bind = op.get_bind()
    inspector = inspect(bind)

    # Check if we're using SQLite
    is_sqlite = bind.dialect.name == 'sqlite'

    if not is_sqlite:
        tables = inspector.get_table_names()

        if 'coverage_snapshots' in tables:
            # Check if foreign keys already exist
            fk_names_ci = [fk['name'] for fk in inspector.get_foreign_keys('ci_runs')]
            if not any('coverage_snapshot' in str(name) for name in fk_names_ci):
                op.create_foreign_key(
                    'fk_ci_runs_coverage_snapshot',
                    'ci_runs',
                    'coverage_snapshots',
                    ['coverage_snapshot_id'],
                    ['id'],
                    ondelete='SET NULL'
                )

            fk_names_tasks = [fk['name'] for fk in inspector.get_foreign_keys('workspace_tasks')]
            if not any('coverage_snapshot' in str(name) for name in fk_names_tasks):
                op.create_foreign_key(
                    'fk_workspace_tasks_coverage_snapshot',
                    'workspace_tasks',
                    'coverage_snapshots',
                    ['coverage_snapshot_id'],
                    ['id'],
                    ondelete='SET NULL'
                )


def downgrade() -> None:
    # Drop foreign key constraints if they exist
    bind = op.get_bind()
    inspector = inspect(bind)

    # Drop foreign keys
    fk_names_ci = [fk['name'] for fk in inspector.get_foreign_keys('ci_runs')]
    if 'fk_ci_runs_coverage_snapshot' in fk_names_ci:
        op.drop_constraint('fk_ci_runs_coverage_snapshot', 'ci_runs', type_='foreignkey')

    fk_names_tasks = [fk['name'] for fk in inspector.get_foreign_keys('workspace_tasks')]
    if 'fk_workspace_tasks_coverage_snapshot' in fk_names_tasks:
        op.drop_constraint('fk_workspace_tasks_coverage_snapshot', 'workspace_tasks', type_='foreignkey')

    # Remove fields from ci_runs table
    if column_exists('ci_runs', 'policy_violations'):
        op.drop_column('ci_runs', 'policy_violations')

    if column_exists('ci_runs', 'policy_passed'):
        op.drop_column('ci_runs', 'policy_passed')

    if column_exists('ci_runs', 'coverage_snapshot_id'):
        op.drop_column('ci_runs', 'coverage_snapshot_id')

    # Remove fields from workspace_tasks table
    if column_exists('workspace_tasks', 'coverage_snapshot_id'):
        op.drop_column('workspace_tasks', 'coverage_snapshot_id')

    if column_exists('workspace_tasks', 'pre_pr_policy_check'):
        op.drop_column('workspace_tasks', 'pre_pr_policy_check')
