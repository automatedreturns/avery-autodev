"""AgentJob model for tracking Celery task execution and providing observability."""

from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, Float
from sqlalchemy.orm import relationship

from app.database import Base


class AgentJob(Base):
    """AgentJob model - tracks async agent processing jobs."""

    __tablename__ = "agent_jobs"

    id = Column(Integer, primary_key=True, index=True)

    # Celery task information
    celery_task_id = Column(String, unique=True, index=True, nullable=False)

    # Related entities
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    task_id = Column(Integer, ForeignKey("workspace_tasks.id", ondelete="CASCADE"), nullable=False)
    user_message_id = Column(Integer, ForeignKey("agent_messages.id", ondelete="SET NULL"), nullable=True)

    # Job status
    status = Column(
        String,
        default="pending",
        nullable=False,
        index=True
    )  # pending, running, completed, failed, cancelled, retrying

    # Timing information
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Duration tracking (in seconds)
    duration = Column(Float, nullable=True)

    # Retry information
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)

    # Error tracking
    error_message = Column(Text, nullable=True)
    error_traceback = Column(Text, nullable=True)

    # Progress tracking
    progress_percentage = Column(Integer, default=0, nullable=False)
    current_iteration = Column(Integer, default=0, nullable=True)
    max_iterations = Column(Integer, default=100, nullable=True)

    # Result summary
    result_summary = Column(Text, nullable=True)  # JSON serialized summary of the result

    # Relationships
    workspace = relationship("Workspace", foreign_keys=[workspace_id])
    task = relationship("WorkspaceTask", foreign_keys=[task_id])
    ci_runs = relationship("CIRun", back_populates="agent_job", cascade="all, delete-orphan")
    # Phase 2 relationships
    agent_test_generations = relationship("AgentTestGeneration", back_populates="agent_job", cascade="all, delete-orphan")

    # Indexes for efficient queries
    __table_args__ = (
        Index('idx_agent_jobs_workspace', 'workspace_id', 'created_at'),
        Index('idx_agent_jobs_task', 'task_id', 'created_at'),
        Index('idx_agent_jobs_status', 'status', 'created_at'),
        Index('idx_agent_jobs_celery_task', 'celery_task_id'),
    )

    def update_status(self, status: str, error_message: str = None, error_traceback: str = None):
        """Update job status with timestamp tracking."""
        self.status = status

        if status == "running" and not self.started_at:
            self.started_at = datetime.utcnow()
        elif status in ["completed", "failed", "cancelled"]:
            if not self.completed_at:
                self.completed_at = datetime.utcnow()
            if self.started_at:
                self.duration = (self.completed_at - self.started_at).total_seconds()

        if error_message:
            self.error_message = error_message
        if error_traceback:
            self.error_traceback = error_traceback

    def update_progress(self, current_iteration: int, max_iterations: int):
        """Update progress tracking."""
        self.current_iteration = current_iteration
        self.max_iterations = max_iterations
        if max_iterations > 0:
            self.progress_percentage = min(100, int((current_iteration / max_iterations) * 100))
