"""add agent_jobs table for celery task tracking

Revision ID: add_agent_jobs_001
Revises: 67bb1fdbf2ba
Create Date: 2025-12-18

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = 'add_agent_jobs_001'
down_revision = '67bb1fdbf2ba'
branch_labels = None
depends_on = None


def table_exists(table_name: str) -> bool:
    """Check if a table exists."""
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def index_exists(index_name: str, table_name: str) -> bool:
    """Check if an index exists on a table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    indexes = inspector.get_indexes(table_name)
    return any(idx['name'] == index_name for idx in indexes)


def upgrade():
    """Create agent_jobs table for tracking Celery task execution."""
    if not table_exists('agent_jobs'):
        op.create_table(
            'agent_jobs',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('celery_task_id', sa.String(), nullable=False),
            sa.Column('workspace_id', sa.Integer(), nullable=False),
            sa.Column('task_id', sa.Integer(), nullable=False),
            sa.Column('user_message_id', sa.Integer(), nullable=True),
            sa.Column('status', sa.String(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('started_at', sa.DateTime(), nullable=True),
            sa.Column('completed_at', sa.DateTime(), nullable=True),
            sa.Column('duration', sa.Float(), nullable=True),
            sa.Column('retry_count', sa.Integer(), nullable=False),
            sa.Column('max_retries', sa.Integer(), nullable=False),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('error_traceback', sa.Text(), nullable=True),
            sa.Column('progress_percentage', sa.Integer(), nullable=False),
            sa.Column('current_iteration', sa.Integer(), nullable=True),
            sa.Column('max_iterations', sa.Integer(), nullable=True),
            sa.Column('result_summary', sa.Text(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['task_id'], ['workspace_tasks.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['user_message_id'], ['agent_messages.id'], ondelete='SET NULL'),
        )

    # Create indexes for efficient queries
    if table_exists('agent_jobs'):
        if not index_exists('idx_agent_jobs_workspace', 'agent_jobs'):
            op.create_index('idx_agent_jobs_workspace', 'agent_jobs', ['workspace_id', 'created_at'])
        if not index_exists('idx_agent_jobs_task', 'agent_jobs'):
            op.create_index('idx_agent_jobs_task', 'agent_jobs', ['task_id', 'created_at'])
        if not index_exists('idx_agent_jobs_status', 'agent_jobs'):
            op.create_index('idx_agent_jobs_status', 'agent_jobs', ['status', 'created_at'])
        if not index_exists('idx_agent_jobs_celery_task', 'agent_jobs'):
            op.create_index('idx_agent_jobs_celery_task', 'agent_jobs', ['celery_task_id'], unique=True)


def downgrade():
    """Drop agent_jobs table and indexes."""
    if table_exists('agent_jobs'):
        if index_exists('idx_agent_jobs_celery_task', 'agent_jobs'):
            op.drop_index('idx_agent_jobs_celery_task', table_name='agent_jobs')
        if index_exists('idx_agent_jobs_status', 'agent_jobs'):
            op.drop_index('idx_agent_jobs_status', table_name='agent_jobs')
        if index_exists('idx_agent_jobs_task', 'agent_jobs'):
            op.drop_index('idx_agent_jobs_task', table_name='agent_jobs')
        if index_exists('idx_agent_jobs_workspace', 'agent_jobs'):
            op.drop_index('idx_agent_jobs_workspace', table_name='agent_jobs')
        op.drop_table('agent_jobs')
