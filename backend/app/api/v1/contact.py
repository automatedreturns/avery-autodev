"""Contact form API endpoints."""

from fastapi import APIRouter, HTTPException, status

from app.schemas.contact import ContactRequest, ContactResponse
from app.services.email_service import send_contact_sales_email

router = APIRouter(prefix="/contact", tags=["contact"])


@router.post("/sales", response_model=ContactResponse)
async def contact_sales(contact_data: ContactRequest):
    """
    Submit a contact sales inquiry.
    Sends an email to hello@goodgist.com with the inquiry details.

    Args:
        contact_data: Contact form data (name, email, company, message)

    Returns:
        Success message

    Raises:
        HTTPException: If email sending fails
    """
    # Send email to sales team
    email_sent = await send_contact_sales_email(
        name=contact_data.name,
        email=contact_data.email,
        company=contact_data.company,
        message=contact_data.message,
    )

    if not email_sent:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send contact inquiry. Please try again later.",
        )

    return ContactResponse(
        message="Thank you for your inquiry! We'll get back to you soon.",
        success=True,
    )
