"""Agent Test Generation model - Phase 2: Tracks automatic test generation by agent."""

from datetime import datetime
from enum import Enum
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    JSON,
)
from sqlalchemy.orm import relationship

from app.database import Base


class TestGenerationStatus(str, Enum):
    """Test generation job status."""
    PENDING = "pending"
    IN_PROGRESS = "generating"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentTestGeneration(Base):
    """Track automatic test generation attempts by the agent (Phase 2)."""

    __tablename__ = "agent_test_generations"

    # Identity
    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    agent_job_id = Column(
        Integer,
        ForeignKey("agent_jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    ci_run_id = Column(
        Integer,
        ForeignKey("ci_runs.id", ondelete="SET NULL"),
        nullable=True
    )

    # Generation Context
    trigger_type = Column(String(50), nullable=False)  # 'feature', 'bug_fix', 'manual'
    source_files = Column(JSON, default=list)  # Files that needed tests
    generated_test_files = Column(JSON, default=list)  # Tests that were generated

    # Status
    status = Column(String(50), default="pending", index=True)
    # Status values: 'pending', 'generating', 'validating', 'completed', 'failed'
    generation_method = Column(String(50))  # 'unit', 'regression', 'integration'

    # Quality Metrics
    tests_generated_count = Column(Integer, default=0)
    tests_passed_count = Column(Integer, default=0)
    tests_failed_count = Column(Integer, default=0)
    test_quality_score = Column(Float, nullable=True)  # 0-100

    # Coverage Impact
    coverage_before = Column(Float, nullable=True)
    coverage_after = Column(Float, nullable=True)
    coverage_delta = Column(Float, nullable=True)

    # Validation
    validation_passed = Column(Boolean, default=False)
    validation_errors = Column(JSON, default=list)

    # Resource Usage
    prompt_tokens_used = Column(Integer, default=0)
    completion_tokens_used = Column(Integer, default=0)
    duration_seconds = Column(Float, nullable=True)

    # Error Handling
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=2)

    # Agent Run Metadata
    agent_run_metadata = Column(JSON, default=dict)  # Stores generation context, requested_by, etc.

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    workspace = relationship("Workspace", back_populates="agent_test_generations")
    agent_job = relationship("AgentJob", back_populates="agent_test_generations")
    ci_run = relationship("CIRun", back_populates="agent_test_generation", uselist=False)
    coverage_snapshot = relationship(
        "CoverageSnapshot",
        back_populates="agent_test_generation",
        uselist=False
    )

    def __repr__(self):
        return (
            f"<AgentTestGeneration(id={self.id}, workspace_id={self.workspace_id}, "
            f"status={self.status}, quality_score={self.test_quality_score})>"
        )

    def can_retry(self) -> bool:
        """Check if this job can be retried."""
        return (
            self.status == "failed" and
            self.retry_count < self.max_retries
        )

    def mark_generating(self):
        """Mark job as generating."""
        self.status = "generating"

    def mark_validating(self):
        """Mark job as validating."""
        self.status = "validating"

    def mark_completed(self, quality_score: float):
        """Mark job as completed."""
        self.status = "completed"
        self.test_quality_score = quality_score
        self.completed_at = datetime.utcnow()

    def mark_failed(self, error_message: str):
        """Mark job as failed."""
        self.status = "failed"
        self.error_message = error_message
        self.retry_count += 1
        self.completed_at = datetime.utcnow()

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "agent_job_id": self.agent_job_id,
            "ci_run_id": self.ci_run_id,
            "trigger_type": self.trigger_type,
            "source_files": self.source_files,
            "generated_test_files": self.generated_test_files,
            "status": self.status,
            "generation_method": self.generation_method,
            "tests_generated_count": self.tests_generated_count,
            "tests_passed_count": self.tests_passed_count,
            "tests_failed_count": self.tests_failed_count,
            "test_quality_score": self.test_quality_score,
            "coverage_before": self.coverage_before,
            "coverage_after": self.coverage_after,
            "coverage_delta": self.coverage_delta,
            "validation_passed": self.validation_passed,
            "validation_errors": self.validation_errors,
            "prompt_tokens_used": self.prompt_tokens_used,
            "completion_tokens_used": self.completion_tokens_used,
            "duration_seconds": self.duration_seconds,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "agent_run_metadata": self.agent_run_metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
