"""Pydantic schemas for workspace task API validation and serialization."""

from datetime import datetime

from pydantic import BaseModel, Field


# Request schema for adding a task
class WorkspaceTaskCreate(BaseModel):
    """Schema for linking a GitHub issue to workspace."""

    github_issue_number: int = Field(..., gt=0, description="GitHub issue number to link")


# Response schema for a task
class WorkspaceTaskResponse(BaseModel):
    """Schema for workspace task in responses."""

    id: int
    workspace_id: int
    github_issue_number: int
    github_issue_title: str | None = None  # Cached for display
    issue_url: str  # Computed field
    added_by_user_id: int
    added_by_username: str  # Denormalized for display
    added_at: datetime

    # Coder Agent fields
    agent_status: str = "idle"  # idle, running, completed, failed
    agent_branch_name: str | None = None
    agent_pr_number: int | None = None
    agent_pr_url: str | None = None
    agent_error: str | None = None
    agent_executed_at: datetime | None = None

    class Config:
        from_attributes = True


# List response with pagination
class WorkspaceTaskListResponse(BaseModel):
    """Schema for workspace task list endpoint response."""

    tasks: list[WorkspaceTaskResponse]
    total: int


# GitHub issue preview (for browsing available issues)
class GitHubIssuePreview(BaseModel):
    """Schema for GitHub issue in available issues list."""

    number: int
    title: str
    state: str  # "open" or "closed"
    html_url: str
    created_at: str
    updated_at: str


# Available issues response
class AvailableIssuesResponse(BaseModel):
    """Schema for listing available GitHub issues."""

    repository: str
    issues: list[GitHubIssuePreview]
    total_count: int
    has_next: bool
    already_linked: list[int]  # Issue numbers already linked to workspace


# Feature request creation schema
class FeatureRequestCreate(BaseModel):
    """Schema for creating a new feature request (GitHub issue + task)."""

    title: str = Field(..., min_length=1, max_length=200, description="Feature request title")
    description: str = Field(..., min_length=1, description="Detailed description of the feature")
    acceptance_criteria: str | None = Field(None, description="Optional acceptance criteria")
    labels: list[str] = Field(default_factory=lambda: ["enhancement"], description="GitHub labels")
    link_as_task: bool = Field(True, description="Automatically link as workspace task after creation")


# Feature request response schema
class FeatureRequestResponse(BaseModel):
    """Schema for feature request creation response."""

    success: bool
    issue_number: int | None = None
    issue_url: str | None = None
    task_id: int | None = None  # If link_as_task=True
    error: str | None = None


# Similar issues search schema
class SimilarIssuesSearch(BaseModel):
    """Schema for searching similar issues."""

    query: str = Field(..., min_length=1, description="Search query (title/body keywords)")
    state: str = Field("open", description="Issue state: open, closed, or all")
    max_results: int = Field(5, ge=1, le=20, description="Maximum results to return")


# Similar issues response schema
class SimilarIssuesResponse(BaseModel):
    """Schema for similar issues search response."""

    repository: str
    issues: list[GitHubIssuePreview]
    total_count: int
    error: str | None = None
