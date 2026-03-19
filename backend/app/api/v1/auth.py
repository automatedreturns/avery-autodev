import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.security import create_access_token, get_password_hash, verify_password
from app.database import get_db
from app.models.magic_link import MagicLinkToken
from app.models.user import User
from app.schemas.magic_link import MagicLinkRequest, MagicLinkResponse, MagicLinkVerify
from app.schemas.token import Token
from app.schemas.user import UserCreate, UserResponse
from app.services.email_service import send_magic_link_email

router = APIRouter(prefix="/auth", tags=["authentication"])

# Initialize OAuth
oauth = OAuth()

# Configure Google OAuth
oauth.register(
    name='google',
    client_id=settings.GOOGLE_CLIENT_ID,
    client_secret=settings.GOOGLE_CLIENT_SECRET,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)


class LoginRequest(BaseModel):
    """Schema for email+password login."""
    email: EmailStr
    password: str


# ─── Auth Features Endpoint ──────────────────────────────────────────

@router.get("/features")
def get_auth_features():
    """Return which authentication methods are enabled."""
    return {
        "password": settings.AUTH_PASSWORD_ENABLED,
        "magic_link": settings.AUTH_MAGIC_LINK_ENABLED,
        "google": settings.AUTH_GOOGLE_ENABLED,
    }


# ─── Password Auth Endpoints ─────────────────────────────────────────

@router.post("/register", response_model=Token)
def register(
    user_data: UserCreate,
    db: Annotated[Session, Depends(get_db)]
):
    """Register a new user with email and password."""
    if not settings.AUTH_PASSWORD_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Password authentication is disabled"
        )

    email = user_data.email.lower()

    # Check if user already exists
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists"
        )

    # Auto-generate username from email
    username = email.split('@')[0]
    base_username = username
    counter = 1
    while db.query(User).filter(User.username == username).first():
        username = f"{base_username}{counter}"
        counter += 1

    user = User(
        email=email,
        username=username,
        hashed_password=get_password_hash(user_data.password),
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Return token so user is logged in immediately after registration
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/login", response_model=Token)
def login(
    login_data: LoginRequest,
    db: Annotated[Session, Depends(get_db)]
):
    """Authenticate with email and password."""
    if not settings.AUTH_PASSWORD_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Password authentication is disabled"
        )

    email = login_data.email.lower()

    user = db.query(User).filter(User.email == email).first()
    if not user or not user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    if not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}


# ─── Magic Link Endpoints ────────────────────────────────────────────

@router.post("/magic-link/request", response_model=MagicLinkResponse)
async def request_magic_link(
    request_data: MagicLinkRequest,
    db: Annotated[Session, Depends(get_db)]
):
    """Request a magic link to be sent to the user's email."""
    if not settings.AUTH_MAGIC_LINK_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Magic link authentication is disabled"
        )

    email = request_data.email.lower()

    # Check if user exists, if not create them
    user = db.query(User).filter(User.email == email).first()
    if not user:
        # Auto-generate username from email
        username = email.split('@')[0]
        base_username = username
        counter = 1
        while db.query(User).filter(User.username == username).first():
            username = f"{base_username}{counter}"
            counter += 1

        user = User(
            email=email,
            username=username,
            hashed_password=None,  # No password for magic link users
            is_active=True
        )
        db.add(user)
        db.commit()

    # Generate secure token
    token = secrets.token_urlsafe(32)

    # Calculate expiration
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.MAGIC_LINK_EXPIRE_MINUTES)

    # Save token to database
    magic_link_token = MagicLinkToken(
        email=email,
        token=token,
        expires_at=expires_at
    )
    db.add(magic_link_token)
    db.commit()

    # Create magic link URL
    magic_link = f"{settings.FRONTEND_URL}/auth/verify?token={token}"

    # Send email
    email_sent = await send_magic_link_email(email, magic_link)

    if not email_sent:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send magic link email"
        )

    return {
        "message": "Magic link sent! Check your email to sign in.",
        "email": email
    }


@router.post("/magic-link/verify", response_model=Token)
def verify_magic_link(
    verify_data: MagicLinkVerify,
    db: Annotated[Session, Depends(get_db)]
):
    """Verify magic link token and return access token."""
    if not settings.AUTH_MAGIC_LINK_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Magic link authentication is disabled"
        )

    # Find token in database
    magic_token = db.query(MagicLinkToken).filter(
        MagicLinkToken.token == verify_data.token
    ).first()

    if not magic_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired magic link"
        )

    # Check if token is already used
    if magic_token.is_used:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This magic link has already been used"
        )

    # Check if token is expired
    if datetime.now(timezone.utc) > magic_token.expires_at.replace(tzinfo=timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This magic link has expired"
        )

    # Mark token as used
    magic_token.is_used = True
    db.commit()

    # Find user
    user = db.query(User).filter(User.email == magic_token.email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )

    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}


# ─── Current User ────────────────────────────────────────────────────

@router.get("/me", response_model=UserResponse)
def get_me(current_user: Annotated[User, Depends(get_current_user)]):
    """Get current authenticated user."""
    return current_user


# ─── Google OAuth Endpoints ──────────────────────────────────────────

@router.get("/google/login")
async def google_login(request: Request):
    """Initiate Google OAuth login flow."""
    if not settings.AUTH_GOOGLE_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Google authentication is disabled"
        )
    redirect_uri = settings.GOOGLE_REDIRECT_URI
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/google/callback")
async def google_callback(request: Request, db: Annotated[Session, Depends(get_db)]):
    """Handle Google OAuth callback and create/login user."""
    if not settings.AUTH_GOOGLE_ENABLED:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/signin?error=google_auth_disabled")

    try:
        # Get OAuth token from Google
        token = await oauth.google.authorize_access_token(request)

        # Get user info from Google
        user_info = token.get('userinfo')
        if not user_info:
            return RedirectResponse(url=f"{settings.FRONTEND_URL}/signin?error=failed_to_get_user_info")

        google_id = user_info.get('sub')
        email = user_info.get('email')
        picture = user_info.get('picture')

        if not google_id or not email:
            return RedirectResponse(url=f"{settings.FRONTEND_URL}/signin?error=missing_user_info")

        # Check if user exists by google_id
        user = db.query(User).filter(User.google_id == google_id).first()

        if not user:
            # Check if user exists by email
            user = db.query(User).filter(User.email == email).first()

            if user:
                # Link Google account to existing user
                user.google_id = google_id
                user.google_email = email
                user.google_picture = picture
            else:
                # Create new user
                username = email.split('@')[0]

                # Ensure unique username
                base_username = username
                counter = 1
                while db.query(User).filter(User.username == username).first():
                    username = f"{base_username}{counter}"
                    counter += 1

                user = User(
                    email=email,
                    username=username,
                    google_id=google_id,
                    google_email=email,
                    google_picture=picture,
                    hashed_password=None,  # OAuth user, no password
                    is_active=True
                )
                db.add(user)

            db.commit()
            db.refresh(user)

        # Create access token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.username},
            expires_delta=access_token_expires
        )

        # Redirect to frontend with token
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/auth/google/callback?token={access_token}")

    except Exception as e:
        error_message = str(e).replace(" ", "_")
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/signin?error={error_message}")
