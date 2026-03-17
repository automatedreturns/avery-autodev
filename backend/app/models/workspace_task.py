"""WorkspaceTask model for linking GitHub issues to workspaces."""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class WorkspaceTask(Base):
    """WorkspaceTask model - links GitHub issues to workspaces."""

    __tablename__ = "workspace_tasks"

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)

    # GitHub Issue Information (minimal - no caching)
    github_issue_number = Column(Integer, nullable=False)
    github_issue_title = Column(String, nullable=True)  # Cached for display

    # Audit fields
    added_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    added_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Coder Agent fields
    agent_status = Column(String, default="idle", nullable=False)  # idle, running, completed, failed
    agent_branch_name = Column(String, nullable=True)
    agent_pr_number = Column(Integer, nullable=True)
    agent_pr_url = Column(String, nullable=True)
    agent_error = Column(Text, nullable=True)
    agent_executed_at = Column(DateTime, nullable=True)
    agent_context = Column(Text, nullable=True)  # JSON serialized user inputs
    local_repo_path = Column(String, nullable=True)  # Local clone path for this task

    # Document attachment processing fields
    attachments_metadata = Column(Text, nullable=True)  # JSON serialized attachment processing results
    attachments_processed_at = Column(DateTime, nullable=True)  # When attachments were last processed

    # Claude Agent SDK session tracking for conversation continuation
    claude_session_id = Column(String, nullable=True)  # Session ID from SDK for resume capability

    # Relationships
    workspace = relationship("Workspace", back_populates="tasks")
    added_by = relationship("User", foreign_keys=[added_by_user_id])

    # Constraints
    __table_args__ = (
        # Prevent duplicate issue links within same workspace
        UniqueConstraint('workspace_id', 'github_issue_number', name='unique_workspace_issue'),
        # Index for efficient queries
        Index('idx_workspace_tasks', 'workspace_id', 'added_at'),
    )

    def get_issue_url(self, github_repository: str, git_provider: str = "github", gitlab_url: str | None = None) -> str:
        """Generate issue URL from repository, provider, and issue number."""
        if git_provider == "gitlab":
            base_url = (gitlab_url or "https://gitlab.com").rstrip("/")
            return f"{base_url}/{github_repository}/-/issues/{self.github_issue_number}"
        return f"https://github.com/{github_repository}/issues/{self.github_issue_number}"
