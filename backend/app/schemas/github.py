"""Pydantic schemas for Git provider API integration (GitHub & GitLab)."""

from pydantic import BaseModel, Field


# Git provider token storage
class GitHubTokenStore(BaseModel):
    """Schema for storing a git provider personal access token."""

    token: str = Field(..., min_length=1)
    github_username: str | None = None  # Optional, will be fetched if not provided
    provider: str = Field(default="github", pattern=r"^(github|gitlab)$")
    gitlab_url: str | None = None  # For self-hosted GitLab instances


class GitHubTokenResponse(BaseModel):
    """Schema for git provider token status response."""

    status: str  # "connected" or "not_connected"
    github_username: str | None = None
    provider: str = "github"


# Repository validation
class GitHubRepoValidation(BaseModel):
    """Schema for repository validation response."""

    valid: bool
    repository: str
    description: str | None = None
    default_branch: str | None = None
    error: str | None = None


# Branches list
class GitHubBranchList(BaseModel):
    """Schema for listing repository branches."""

    repository: str
    branches: list[str]
