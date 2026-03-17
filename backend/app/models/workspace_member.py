"""WorkspaceMember model for managing workspace collaborators with roles."""

from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class WorkspaceMemberRole(str, Enum):
    """Enum for workspace member roles."""

    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class WorkspaceMember(Base):
    """WorkspaceMember model for database - join table with additional fields."""

    __tablename__ = "workspace_members"

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(String, nullable=False, default=WorkspaceMemberRole.MEMBER.value)

    # Default workspace flag (one per user)
    is_default = Column(Boolean, default=False)

    # Timestamps
    joined_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    workspace = relationship("Workspace", back_populates="members")
    user = relationship("User", back_populates="workspace_memberships")

    # Constraints
    __table_args__ = (
        UniqueConstraint('workspace_id', 'user_id', name='unique_workspace_user'),
        Index('idx_user_default', 'user_id', 'is_default'),
    )
