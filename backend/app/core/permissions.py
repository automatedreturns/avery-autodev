"""Permission checking dependencies for workspace access control."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember, WorkspaceMemberRole


def get_workspace_or_403(
    workspace_id: int,
    db: Session,
    current_user: User,
) -> tuple[Workspace, WorkspaceMember]:
    """
    Get workspace and verify user is a member.

    Args:
        workspace_id: Workspace ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        Tuple of (workspace, membership)

    Raises:
        HTTPException: 404 if workspace not found, 403 if user is not a member
    """
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    # Check if user is a member
    membership = (
        db.query(WorkspaceMember)
        .filter(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == current_user.id,
        )
        .first()
    )

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this workspace",
        )

    return workspace, membership


def require_workspace_admin(
    workspace_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> tuple[Workspace, WorkspaceMember]:
    """
    Verify user is admin or owner of workspace.

    Args:
        workspace_id: Workspace ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        Tuple of (workspace, membership)

    Raises:
        HTTPException: If user is not admin or owner
    """
    workspace, membership = get_workspace_or_403(workspace_id, db, current_user)

    if membership.role not in [WorkspaceMemberRole.ADMIN.value, WorkspaceMemberRole.OWNER.value]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or owner permission required",
        )

    return workspace, membership


def require_workspace_owner(
    workspace_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> tuple[Workspace, WorkspaceMember]:
    """
    Verify user is owner of workspace.

    Args:
        workspace_id: Workspace ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        Tuple of (workspace, membership)

    Raises:
        HTTPException: If user is not owner
    """
    workspace, membership = get_workspace_or_403(workspace_id, db, current_user)

    if membership.role != WorkspaceMemberRole.OWNER.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner permission required",
        )

    return workspace, membership
