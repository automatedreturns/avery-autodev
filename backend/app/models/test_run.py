"""Test Run model for tracking test execution history."""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class TestRun(Base):
    """
    Test Run model representing an execution of a test suite.
    Tracks test results, coverage, and execution metadata.
    """

    __tablename__ = "test_runs"

    id = Column(Integer, primary_key=True, index=True)
    test_suite_id = Column(Integer, ForeignKey("test_suites.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_task_id = Column(Integer, ForeignKey("workspace_tasks.id", ondelete="SET NULL"), nullable=True, index=True)
    branch_name = Column(String(255), nullable=False)
    trigger_type = Column(String(50), nullable=False)  # manual, auto, pre-pr, scheduled
    status = Column(String(50), default="queued")  # queued, running, completed, failed, cancelled
    total_tests = Column(Integer, default=0)
    passed_tests = Column(Integer, default=0)
    failed_tests = Column(Integer, default=0)
    skipped_tests = Column(Integer, default=0)
    duration_seconds = Column(Float, nullable=True)
    coverage_percentage = Column(Float, nullable=True)
    error_message = Column(String(1000), nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    triggered_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    # Relationships
    test_suite = relationship("TestSuite", back_populates="test_runs")
    workspace_task = relationship("WorkspaceTask", foreign_keys=[workspace_task_id])
    triggered_by_user = relationship("User", foreign_keys=[triggered_by])
    test_results = relationship("TestResult", back_populates="test_run", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<TestRun(id={self.id}, suite_id={self.test_suite_id}, status='{self.status}')>"
