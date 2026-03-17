"""Pydantic schemas for coder agent API validation and serialization."""

from datetime import datetime

from pydantic import BaseModel, Field


# Request schema for executing coder agent
class CoderAgentExecuteRequest(BaseModel):
    """Schema for executing coder agent on a task."""

    additional_context: str = Field(default="", description="Additional context or instructions for the agent")
    target_branch: str | None = Field(default=None, description="Target branch to create from (defaults to workspace dev branch)")
    files_to_modify: list[str] | None = Field(default=None, description="Specific files to modify (optional)")


# Response schema for agent execution
class CoderAgentExecuteResponse(BaseModel):
    """Schema for coder agent execution response."""

    status: str  # "started", "error"
    message: str
    task_id: int


# Response schema for agent status
class CoderAgentStatusResponse(BaseModel):
    """Schema for coder agent status response."""

    status: str  # idle, running, completed, failed
    branch_name: str | None = None
    pr_number: int | None = None
    pr_url: str | None = None
    error: str | None = None
    executed_at: datetime | None = None
