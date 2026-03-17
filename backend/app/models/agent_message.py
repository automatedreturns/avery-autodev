"""AgentMessage model for storing chat history with the coder agent."""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class AgentMessage(Base):
    """AgentMessage model - stores chat messages between user and agent."""

    __tablename__ = "agent_messages"

    id = Column(Integer, primary_key=True, index=True)
    workspace_task_id = Column(Integer, ForeignKey("workspace_tasks.id", ondelete="CASCADE"), nullable=False)

    # Message details
    role = Column(String, nullable=False)  # "user", "assistant", "system"
    content = Column(Text, nullable=False)
    attachments = Column(Text, nullable=True)  # JSON string storing file attachment metadata

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # null for system/assistant messages

    # Relationships
    task = relationship("WorkspaceTask")
    user = relationship("User", foreign_keys=[user_id])

    # Indexes
    __table_args__ = (
        Index('idx_agent_messages_task', 'workspace_task_id', 'created_at'),
    )
