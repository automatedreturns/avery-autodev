from datetime import datetime
import re

from pydantic import BaseModel, EmailStr, field_validator


class UserBase(BaseModel):
    """Base user schema with common attributes."""
    email: EmailStr
    username: str


class UserCreate(BaseModel):
    """Schema for creating a new user (username auto-generated from email)."""
    email: EmailStr
    password: str

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        """
        Validate password meets security requirements.

        Requirements:
        - At least 8 characters
        - At least one uppercase letter
        - At least one lowercase letter
        - At least one number
        - At least one special character
        """
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'[0-9]', v):
            raise ValueError('Password must contain at least one number')
        if not re.search(r'[^A-Za-z0-9]', v):
            raise ValueError('Password must contain at least one special character')
        return v


class UserUpdate(BaseModel):
    """Schema for updating user data."""
    email: EmailStr | None = None
    username: str | None = None
    password: str | None = None


class UserResponse(UserBase):
    """Schema for user response (returned to client)."""
    id: int
    is_active: bool
    created_at: datetime
    github_username: str | None = None
    gitlab_username: str | None = None
    gitlab_url: str | None = None

    class Config:
        from_attributes = True


class UserInDB(UserBase):
    """Schema for user in database (includes hashed password)."""
    id: int
    hashed_password: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True
