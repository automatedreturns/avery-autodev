"""Pydantic schemas for agent message API validation and serialization."""

from datetime import datetime

from pydantic import BaseModel, Field


# Request schema for sending a message
class AgentMessageCreate(BaseModel):
    """Schema for creating a new agent message."""

    content: str = Field(..., min_length=1, max_length=10000, description="Message content")


# File attachment schema
class FileAttachment(BaseModel):
    """Schema for file attachment metadata."""

    filename: str
    file_path: str
    file_size: int
    content_type: str


# Response schema for a message
class AgentMessageResponse(BaseModel):
    """Schema for agent message in responses."""

    id: int
    workspace_task_id: int
    role: str  # "user", "assistant", "system"
    content: str
    attachments: list[FileAttachment] | None = None
    created_at: datetime
    user_id: int | None
    username: str | None  # Denormalized for display

    class Config:
        from_attributes = True


# List response
class AgentMessageListResponse(BaseModel):
    """Schema for agent message list endpoint response."""

    messages: list[AgentMessageResponse]
    total: int
