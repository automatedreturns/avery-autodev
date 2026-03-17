"""Pydantic schemas for workspace API validation and serialization."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


# Base schema with common fields
class WorkspaceBase(BaseModel):
    """Base workspace schema with common attributes."""

    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    git_provider: str = Field(default="github", pattern=r"^(github|gitlab)$")
    gitlab_url: str | None = None  # For self-hosted GitLab (only used when git_provider=gitlab)
    github_repository: str = Field(..., min_length=3)  # Format: "owner/repo" or "namespace/project"
    github_dev_branch: str = Field(..., min_length=1)
    github_main_branch: str = Field(..., min_length=1)

    @field_validator('github_repository')
    @classmethod
    def validate_repo_format(cls, v: str) -> str:
        """Validate repository format (works for both GitHub and GitLab)."""
        if not v or '/' not in v:
            raise ValueError('Repository must be in format: owner/repo or namespace/project')
        parts = v.split('/')
        if len(parts) < 2 or not parts[0] or not parts[-1]:
            raise ValueError('Repository must be in format: owner/repo or namespace/project')
        return v


# Create schema for POST /workspaces
class WorkspaceCreate(WorkspaceBase):
    """Schema for creating a new workspace."""

    pass


# Update schema for PUT /workspaces/{id}
class WorkspaceUpdate(BaseModel):
    """Schema for updating a workspace - all fields optional."""

    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    github_dev_branch: str | None = Field(None, min_length=1)
    github_main_branch: str | None = Field(None, min_length=1)
    is_active: bool | None = None


# Member schema for nested representation
class MemberResponse(BaseModel):
    """Schema for workspace member in responses."""

    id: int
    user_id: int
    username: str
    email: str
    role: str
    joined_at: datetime
    # Git provider status (optional, for new member additions)
    has_github: bool | None = None
    github_username: str | None = None

    class Config:
        from_attributes = True


class AddMemberResponse(MemberResponse):
    """Schema for add member response with additional access info."""

    # Warning message if there are access concerns
    warning: str | None = None

    class Config:
        from_attributes = True


# Basic workspace response for list view
class WorkspaceResponse(BaseModel):
    """Schema for workspace in list responses."""

    id: int
    name: str
    git_provider: str = "github"
    github_repository: str
    github_dev_branch: str
    github_main_branch: str
    is_active: bool
    owner_id: int
    created_at: datetime
    updated_at: datetime
    role: str  # Current user's role in this workspace
    is_default: bool  # Is this the user's default workspace

    class Config:
        from_attributes = True


# Detailed workspace response with members
class WorkspaceDetail(WorkspaceResponse):
    """Schema for detailed workspace view including members."""

    description: str | None
    gitlab_url: str | None = None
    owner: dict  # Owner user info
    members: list[MemberResponse]
    member_count: int
    polling_enabled: bool = False

    class Config:
        from_attributes = True


# List response with pagination
class WorkspaceListResponse(BaseModel):
    """Schema for workspace list endpoint response."""

    workspaces: list[WorkspaceResponse]
    total: int


# Member management schemas
class AddMemberRequest(BaseModel):
    """Schema for adding a member to workspace."""

    user_id: int = Field(..., gt=0)
    role: str = Field(..., pattern=r"^(admin|member)$")

    @field_validator('role')
    @classmethod
    def validate_role(cls, v: str) -> str:
        """Validate role is not 'owner' (assigned automatically)."""
        if v == "owner":
            raise ValueError("Cannot manually assign owner role")
        return v


class UpdateMemberRoleRequest(BaseModel):
    """Schema for updating member role."""

    role: str = Field(..., pattern=r"^(admin|member)$")


class SetDefaultWorkspaceResponse(BaseModel):
    """Schema for set default workspace response."""

    workspace_id: int
    is_default: bool
