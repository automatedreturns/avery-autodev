"""Schemas for magic link authentication."""

from pydantic import BaseModel, EmailStr


class MagicLinkRequest(BaseModel):
    """Request schema for magic link."""
    email: EmailStr


class MagicLinkResponse(BaseModel):
    """Response schema for magic link request."""
    message: str
    email: str


class MagicLinkVerify(BaseModel):
    """Request schema for verifying magic link token."""
    token: str
