"""Test Suite model for managing test configurations within workspaces."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class TestSuite(Base):
    """
    Test Suite model representing a collection of tests for a workspace.
    Each workspace can have multiple test suites (e.g., unit tests, integration tests).
    """

    __tablename__ = "test_suites"

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    test_framework = Column(String(50), nullable=False)  # pytest, jest, mocha, junit, etc.
    test_directory = Column(String(500), nullable=False)  # relative path in repo, e.g., "tests/"
    coverage_threshold = Column(Float, default=80.0)  # Minimum coverage percentage required
    is_active = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    workspace = relationship("Workspace", back_populates="test_suites")
    creator = relationship("User", foreign_keys=[created_by])
    test_cases = relationship("TestCase", back_populates="test_suite", cascade="all, delete-orphan")
    test_runs = relationship("TestRun", back_populates="test_suite", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<TestSuite(id={self.id}, name='{self.name}', workspace_id={self.workspace_id})>"
