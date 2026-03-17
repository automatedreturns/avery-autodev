"""CI Run model for tracking GitHub Actions CI runs."""

from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Integer, String, Text, ForeignKey, JSON, Boolean, Float, Index
from sqlalchemy.orm import relationship

from app.database import Base


class CIRun(Base):
    """
    Track GitHub Actions CI runs for agent-generated PRs.

    This model stores information about CI/CD pipeline executions,
    their results, and enables the agent to read failures and self-fix.
    """

    __tablename__ = "ci_runs"

    id = Column(Integer, primary_key=True, index=True)

    # Related entities
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_job_id = Column(Integer, ForeignKey("agent_jobs.id", ondelete="CASCADE"), nullable=True, index=True)

    # GitHub information
    repository = Column(String(500), nullable=False)  # Format: "owner/repo"
    pr_number = Column(Integer, nullable=True, index=True)  # Nullable for push events (non-PR builds)
    branch_name = Column(String(255), nullable=False)
    commit_sha = Column(String(40), nullable=False)

    # GitHub Actions run information
    run_id = Column(String(100), nullable=False, index=True)  # GitHub Actions run ID
    job_name = Column(String(200), nullable=False)  # e.g., "test-backend", "test-frontend"
    workflow_name = Column(String(200), nullable=False, default="Agent PR Validation")

    # Status tracking
    status = Column(String(50), nullable=False, index=True)  # queued, in_progress, completed
    conclusion = Column(String(50), nullable=True)  # success, failure, cancelled, skipped

    # Timestamps
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)

    # Results and logs
    logs_url = Column(Text, nullable=True)
    check_results = Column(JSON, nullable=True)  # Individual check results (tests, lint, typecheck, etc.)
    error_summary = Column(Text, nullable=True)  # Human-readable error summary
    raw_logs = Column(Text, nullable=True)  # Store relevant log excerpts

    # Test coverage (if available)
    coverage_before = Column(Float, nullable=True)
    coverage_after = Column(Float, nullable=True)
    coverage_delta = Column(Float, nullable=True)
    coverage_report_url = Column(Text, nullable=True)

    # Self-fix tracking
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)
    self_fix_attempted = Column(Boolean, default=False, nullable=False)
    self_fix_successful = Column(Boolean, nullable=True)  # null = not attempted, true/false = result

    # Quality metrics
    tests_total = Column(Integer, nullable=True)
    tests_passed = Column(Integer, nullable=True)
    tests_failed = Column(Integer, nullable=True)
    tests_skipped = Column(Integer, nullable=True)

    lint_errors_count = Column(Integer, nullable=True)
    type_errors_count = Column(Integer, nullable=True)

    # Audit
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    workspace = relationship("Workspace", back_populates="ci_runs")
    agent_job = relationship("AgentJob", back_populates="ci_runs")
    # Phase 2 relationships
    agent_test_generation = relationship("AgentTestGeneration", back_populates="ci_run", uselist=False)
    coverage_snapshot = relationship("CoverageSnapshot", back_populates="ci_run", uselist=False)

    # Indexes for efficient queries
    __table_args__ = (
        Index('idx_ci_runs_workspace_pr', 'workspace_id', 'pr_number'),
        Index('idx_ci_runs_status', 'status', 'created_at'),
        Index('idx_ci_runs_conclusion', 'conclusion', 'created_at'),
        Index('idx_ci_runs_agent_job', 'agent_job_id', 'created_at'),
    )

    def __repr__(self):
        return f"<CIRun(id={self.id}, pr_number={self.pr_number}, status='{self.status}', conclusion='{self.conclusion}')>"

    def update_status(self, status: str, conclusion: str = None):
        """Update CI run status with automatic timestamp tracking."""
        self.status = status

        if status == "in_progress" and not self.started_at:
            self.started_at = datetime.now(timezone.utc)
        elif status == "completed":
            if not self.completed_at:
                self.completed_at = datetime.now(timezone.utc)
            if self.started_at:
                self.duration_seconds = (self.completed_at - self.started_at).total_seconds()

        if conclusion:
            self.conclusion = conclusion

    def calculate_coverage_delta(self):
        """Calculate coverage delta if both before and after are available."""
        if self.coverage_before is not None and self.coverage_after is not None:
            self.coverage_delta = round(self.coverage_after - self.coverage_before, 2)

    def is_passing(self) -> bool:
        """Check if CI run passed all checks."""
        return self.status == "completed" and self.conclusion == "success"

    def is_failing(self) -> bool:
        """Check if CI run failed."""
        return self.status == "completed" and self.conclusion == "failure"

    def can_retry(self) -> bool:
        """Check if this CI run can be retried (self-fixed)."""
        return self.is_failing() and self.retry_count < self.max_retries and not self.self_fix_attempted
