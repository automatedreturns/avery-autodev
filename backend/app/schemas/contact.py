"""Contact form schemas."""

from pydantic import BaseModel, EmailStr


class ContactRequest(BaseModel):
    """Request schema for contact sales form."""

    name: str
    email: EmailStr
    company: str = ""
    message: str


class ContactResponse(BaseModel):
    """Response schema for contact sales submission."""

    message: str
    success: bool
