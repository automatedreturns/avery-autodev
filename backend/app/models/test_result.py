"""Test Result model for individual test execution results."""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class TestResult(Base):
    """
    Test Result model representing the outcome of a single test execution.
    Stores pass/fail status, error messages, and execution details.
    """

    __tablename__ = "test_results"

    id = Column(Integer, primary_key=True, index=True)
    test_run_id = Column(Integer, ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    test_case_id = Column(Integer, ForeignKey("test_cases.id", ondelete="SET NULL"), nullable=True, index=True)
    test_name = Column(String(500), nullable=False)
    file_path = Column(String(500), nullable=False)
    status = Column(String(50), nullable=False)  # passed, failed, skipped, error
    duration_seconds = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)
    stack_trace = Column(Text, nullable=True)
    output = Column(Text, nullable=True)  # stdout/stderr
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    # Relationships
    test_run = relationship("TestRun", back_populates="test_results")
    test_case = relationship("TestCase", back_populates="test_results")

    def __repr__(self):
        return f"<TestResult(id={self.id}, test='{self.test_name}', status='{self.status}')>"
