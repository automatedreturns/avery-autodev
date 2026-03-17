"""Test Generation Job model for tracking code generation progress."""

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class TestGenerationJob(Base):
    """Model for tracking test code generation jobs."""

    __tablename__ = "test_generation_jobs"

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    test_suite_id = Column(Integer, ForeignKey("test_suites.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Job status: pending, running, completed, failed
    status = Column(String(50), default="pending", nullable=False, index=True)

    # Progress tracking
    total_tests = Column(Integer, default=0, nullable=False)
    completed_tests = Column(Integer, default=0, nullable=False)
    current_test_name = Column(String(255), nullable=True)

    # Current stage: cloning, generating, committing, pushing, completed
    current_stage = Column(String(50), default="pending", nullable=False)

    # Results
    branch_name = Column(String(255), nullable=True)
    base_branch = Column(String(255), nullable=True)
    generated_files = Column(JSON, nullable=True)  # List of file paths
    pr_url = Column(String(500), nullable=True)

    # Error tracking
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    workspace = relationship("Workspace", back_populates="test_generation_jobs")
    test_suite = relationship("TestSuite")
    user = relationship("User")
