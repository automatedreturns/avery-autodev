"""Polling History model for tracking automatic issue polling and linking."""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class PollingHistory(Base):
    """PollingHistory model - tracks issue polling events."""

    __tablename__ = "polling_history"

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)

    # Polling results
    issues_found = Column(Integer, default=0, nullable=False)
    issues_linked = Column(Integer, default=0, nullable=False)
    issues_skipped = Column(Integer, default=0, nullable=False)
    issues_deferred = Column(Integer, default=0, nullable=False)
    deferred_issue_numbers = Column(Text, nullable=True)  # JSON: [123, 456]

    # Status
    success = Column(String, nullable=False)  # "success" or "error"
    error_message = Column(Text, nullable=True)

    # Linked issue numbers (JSON serialized list)
    linked_issue_numbers = Column(Text, nullable=True)  # JSON: [123, 124, 125]

    # Triggered by
    triggered_by = Column(String, nullable=False)  # "automatic", "manual", "user_id:123"

    # Timestamp
    polled_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    workspace = relationship("Workspace", foreign_keys=[workspace_id])
