"""Workspace token service for managing GitHub token access in shared workspaces.

This service implements a workspace-level token strategy where operations
use the workspace owner's GitHub token, allowing shared workspace members
(admins/members) to perform operations even if they don't have direct
repository access.
"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.workspace import Workspace
from app.services.encryption_service import decrypt_token


class WorkspaceTokenError(Exception):
    """Exception raised when workspace token cannot be retrieved."""
    pass


def get_workspace_github_token(
    db: Session,
    workspace: Workspace,
    current_user: User | None = None,
) -> str:
    """
    Get the GitHub token to use for workspace operations.

    Strategy:
    1. Use workspace owner's token (primary - enables shared access)
    2. If owner's token is unavailable/invalid, fall back to current user's token
    3. Raise error if no valid token is available

    Args:
        db: Database session
        workspace: Workspace object
        current_user: Current authenticated user (optional, for fallback)

    Returns:
        Decrypted GitHub token string

    Raises:
        WorkspaceTokenError: If no valid token is available
    """
    # Determine which provider token to use
    provider = getattr(workspace, "git_provider", None) or "github"
    token_field = "gitlab_token_encrypted" if provider == "gitlab" else "github_token_encrypted"
    provider_name = provider.capitalize()

    # Strategy 1: Use workspace owner's token (enables shared access)
    owner = db.query(User).filter(User.id == workspace.owner_id).first()

    if owner and getattr(owner, token_field, None):
        try:
            token = decrypt_token(getattr(owner, token_field))
            if token:
                return token
        except Exception:
            # Owner's token is invalid/corrupted, try fallback
            pass

    # Strategy 2: Fall back to current user's token if available
    if current_user and getattr(current_user, token_field, None):
        try:
            token = decrypt_token(getattr(current_user, token_field))
            if token:
                return token
        except Exception:
            pass

    # No valid token available
    raise WorkspaceTokenError(
        f"No valid {provider_name} token available for this workspace. "
        f"The workspace owner must have a connected {provider_name} account with repository access."
    )


def get_workspace_github_token_or_403(
    db: Session,
    workspace: Workspace,
    current_user: User | None = None,
) -> str:
    """
    Get the GitHub token for workspace operations, raising HTTP 403 on failure.

    This is a convenience wrapper around get_workspace_github_token that
    raises an HTTPException instead of WorkspaceTokenError.

    Args:
        db: Database session
        workspace: Workspace object
        current_user: Current authenticated user (optional, for fallback)

    Returns:
        Decrypted GitHub token string

    Raises:
        HTTPException: 403 if no valid token is available
    """
    try:
        return get_workspace_github_token(db, workspace, current_user)
    except WorkspaceTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )


def validate_user_has_github_token(user: User) -> None:
    """
    Validate that a user has a GitHub token connected.

    This is useful for operations that specifically require the current
    user's own token (e.g., creating workspaces, validating their own access).

    Args:
        user: User to validate

    Raises:
        HTTPException: 400 if user doesn't have GitHub connected
    """
    if not user.github_token_encrypted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub account not connected. Please connect your GitHub account first.",
        )


def get_user_github_token(user: User) -> str:
    """
    Get a user's own GitHub token.

    Args:
        user: User whose token to retrieve

    Returns:
        Decrypted GitHub token string

    Raises:
        HTTPException: 400 if user doesn't have GitHub connected or token is invalid
    """
    validate_user_has_github_token(user)

    try:
        token = decrypt_token(user.github_token_encrypted)
        if not token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="GitHub token is invalid. Please reconnect your GitHub account.",
            )
        return token
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to decrypt GitHub token. Please reconnect your GitHub account.",
        )


def check_workspace_github_access(db: Session, workspace: Workspace) -> dict:
    """
    Check if the workspace has valid GitHub access through its owner.

    This is useful for providing informative messages to users about
    workspace access status.

    Args:
        db: Database session
        workspace: Workspace to check

    Returns:
        dict with:
        - has_access: bool indicating if workspace has valid GitHub access
        - owner_has_token: bool indicating if owner has GitHub connected
        - message: Human-readable status message
    """
    provider = getattr(workspace, "git_provider", None) or "github"
    token_field = "gitlab_token_encrypted" if provider == "gitlab" else "github_token_encrypted"
    provider_name = provider.capitalize()

    owner = db.query(User).filter(User.id == workspace.owner_id).first()

    if not owner:
        return {
            "has_access": False,
            "owner_has_token": False,
            "message": "Workspace owner not found.",
        }

    if not getattr(owner, token_field, None):
        return {
            "has_access": False,
            "owner_has_token": False,
            "message": f"Workspace owner has not connected their {provider_name} account. "
                      f"{provider_name} features will not work until the owner connects {provider_name}.",
        }

    try:
        token = decrypt_token(getattr(owner, token_field))
        if token:
            return {
                "has_access": True,
                "owner_has_token": True,
                "message": f"Workspace has valid {provider_name} access through the owner.",
            }
    except Exception:
        pass

    return {
        "has_access": False,
        "owner_has_token": True,
        "message": f"Workspace owner's {provider_name} token is invalid. "
                  f"The owner should reconnect their {provider_name} account.",
    }


def get_member_github_status(user: User) -> dict:
    """
    Get the GitHub connection status for a user/member.

    Args:
        user: User to check

    Returns:
        dict with:
        - has_github: bool indicating if user has GitHub connected
        - github_username: GitHub username if connected, None otherwise
    """
    return {
        "has_github": bool(user.github_token_encrypted),
        "github_username": user.github_username,
    }
