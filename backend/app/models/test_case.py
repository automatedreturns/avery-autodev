"""Test Case model for individual test definitions."""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import relationship

from app.database import Base


class TestCase(Base):
    """
    Test Case model representing an individual test within a test suite.
    Stores test metadata, mock data configuration, and assertions.
    """

    __tablename__ = "test_cases"

    id = Column(Integer, primary_key=True, index=True)
    test_suite_id = Column(Integer, ForeignKey("test_suites.id", ondelete="CASCADE"), nullable=False, index=True)
    file_path = Column(String(500), nullable=False)  # relative path, e.g., "tests/test_auth.py"
    test_name = Column(String(255), nullable=False)  # e.g., "test_login_success"
    test_type = Column(String(50), nullable=False)  # unit, integration, e2e, performance
    description = Column(Text, nullable=True)
    mock_data = Column(JSON, nullable=True)  # Mock data configuration as JSON
    assertions = Column(JSON, nullable=True)  # Expected outcomes and assertions
    status = Column(String(50), default="active")  # active, disabled, deprecated
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    test_suite = relationship("TestSuite", back_populates="test_cases")
    test_results = relationship("TestResult", back_populates="test_case")

    def __repr__(self):
        return f"<TestCase(id={self.id}, name='{self.test_name}', type='{self.test_type}')>"
