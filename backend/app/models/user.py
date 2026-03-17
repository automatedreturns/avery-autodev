from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    """User model for database."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=True)  # Nullable for OAuth users
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Google OAuth Integration
    google_id = Column(String, unique=True, nullable=True, index=True)
    google_email = Column(String, nullable=True)
    google_picture = Column(String, nullable=True)

    # GitHub Integration
    github_token_encrypted = Column(String, nullable=True)
    github_username = Column(String, nullable=True)

    # GitLab Integration
    gitlab_token_encrypted = Column(String, nullable=True)
    gitlab_username = Column(String, nullable=True)
    gitlab_url = Column(String, nullable=True)  # For self-hosted instances (default: https://gitlab.com)

    # Relationships
    owned_workspaces = relationship("Workspace", back_populates="owner", foreign_keys="Workspace.owner_id")
    workspace_memberships = relationship("WorkspaceMember", back_populates="user")
    subscription = relationship("Subscription", back_populates="user", uselist=False, cascade="all, delete-orphan")
