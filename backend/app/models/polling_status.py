"""Polling Status model for tracking workspace polling state."""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class PollingStatus(Base):
    """PollingStatus model - tracks current polling state per workspace."""

    __tablename__ = "polling_status"

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, unique=True)

    # Last poll information
    last_poll_time = Column(DateTime, nullable=True)

    # Cumulative stats
    total_issues_imported = Column(Integer, default=0, nullable=False)

    # Last poll results - Issues
    last_poll_issues_found = Column(Integer, default=0, nullable=False)
    last_poll_issues_linked = Column(Integer, default=0, nullable=False)
    last_poll_issues_skipped = Column(Integer, default=0, nullable=False)

    # Last poll results - Deferred (blocked by dependency)
    last_poll_issues_deferred = Column(Integer, default=0, nullable=False)
    last_poll_deferred_issue_numbers = Column(Text, nullable=True)  # JSON: [123, 456]

    # Last poll results - PRs
    last_poll_prs_checked = Column(Integer, default=0, nullable=False)
    last_poll_prs_with_conflicts = Column(Integer, default=0, nullable=False)
    total_pr_tasks_created = Column(Integer, default=0, nullable=False)

    # Status
    last_poll_status = Column(String, default="never", nullable=False)  # "success", "error", "never"
    last_poll_error = Column(Text, nullable=True)

    # Timestamp
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    workspace = relationship("Workspace", foreign_keys=[workspace_id])
