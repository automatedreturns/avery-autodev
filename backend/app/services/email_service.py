"""Email service for sending magic link authentication emails."""

import logging

import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger(__name__)


async def send_magic_link_email(to_email: str, magic_link: str) -> bool:
    """
    Send a magic link email to the user.

    Args:
        to_email: Recipient email address
        magic_link: The magic link URL for authentication

    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        # Create message
        message = MIMEMultipart("alternative")
        message["Subject"] = "Your Avery Login Link"
        message["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
        message["To"] = to_email

        # Create HTML and text versions
        text_content = f"""
Hello,

Click the link below to sign in to your Avery account:

{magic_link}

This link will expire in {settings.MAGIC_LINK_EXPIRE_MINUTES} minutes.

If you didn't request this link, you can safely ignore this email.

Best regards,
The Avery Team
"""

        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background-color: #f8f9fa; border-radius: 10px; padding: 30px; margin: 20px 0;">
        <h2 style="color: #2c3e50; margin-top: 0;">Sign in to Avery</h2>
        <p>Click the button below to sign in to your account:</p>

        <div style="text-align: center; margin: 30px 0;">
            <a href="{magic_link}"
               style="background-color: #007bff; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold;">
                Sign In to Avery
            </a>
        </div>

        <p style="color: #666; font-size: 14px;">
            Or copy and paste this link into your browser:<br>
            <a href="{magic_link}" style="color: #007bff; word-break: break-all;">{magic_link}</a>
        </p>

        <p style="color: #666; font-size: 14px; margin-top: 30px;">
            This link will expire in <strong>{settings.MAGIC_LINK_EXPIRE_MINUTES} minutes</strong>.
        </p>

        <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">

        <p style="color: #999; font-size: 12px;">
            If you didn't request this link, you can safely ignore this email.
        </p>
    </div>
</body>
</html>
"""

        # Attach parts
        part1 = MIMEText(text_content, "plain")
        part2 = MIMEText(html_content, "html")
        message.attach(part1)
        message.attach(part2)

        # Send email
        # Note: For Office365 SMTP on port 587, use start_tls instead of use_tls
        # start_tls uses STARTTLS (upgrade plain connection), use_tls uses direct TLS (port 465)
        await aiosmtplib.send(
            message,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            start_tls=settings.SMTP_USE_TLS,
        )

        return True

    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {str(e)}")
        return False


async def send_contact_sales_email(name: str, email: str, company: str, message: str) -> bool:
    """
    Send a contact sales inquiry to hello@goodgist.com.

    Args:
        name: Name of the person contacting
        email: Email address of the person contacting
        company: Company name (optional)
        message: Message content

    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        # Create message
        email_message = MIMEMultipart("alternative")
        email_message["Subject"] = f"Avery Contact Sales: {name} from {company or 'N/A'}"
        email_message["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
        email_message["To"] = "hello@goodgist.com"
        email_message["Reply-To"] = email

        # Create HTML and text versions
        text_content = f"""
New Contact Sales Inquiry

Name: {name}
Email: {email}
Company: {company or 'N/A'}

Message:
{message}

---
This inquiry was submitted through the Avery contact form.
"""

        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background-color: #f8f9fa; border-radius: 10px; padding: 30px; margin: 20px 0;">
        <h2 style="color: #2c3e50; margin-top: 0;">New Contact Sales Inquiry</h2>

        <div style="background-color: white; padding: 20px; border-radius: 5px; margin: 20px 0;">
            <p style="margin: 10px 0;"><strong>Name:</strong> {name}</p>
            <p style="margin: 10px 0;"><strong>Email:</strong> <a href="mailto:{email}" style="color: #007bff;">{email}</a></p>
            <p style="margin: 10px 0;"><strong>Company:</strong> {company or 'N/A'}</p>
        </div>

        <div style="background-color: white; padding: 20px; border-radius: 5px; margin: 20px 0;">
            <p style="margin: 0 0 10px 0;"><strong>Message:</strong></p>
            <p style="margin: 0; white-space: pre-wrap;">{message}</p>
        </div>

        <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">

        <p style="color: #999; font-size: 12px;">
            This inquiry was submitted through the Avery contact form.
        </p>
    </div>
</body>
</html>
"""

        # Attach parts
        part1 = MIMEText(text_content, "plain")
        part2 = MIMEText(html_content, "html")
        email_message.attach(part1)
        email_message.attach(part2)

        # Send email
        await aiosmtplib.send(
            email_message,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            start_tls=settings.SMTP_USE_TLS,
        )

        return True

    except Exception as e:
        logger.error(f"Failed to send contact sales email: {str(e)}")
        return False
