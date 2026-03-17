"""API endpoints for GitHub issue polling and auto-linking."""

import json
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.permissions import get_workspace_or_403
from app.database import get_db
from app.models.user import User
from app.models.polling_status import PollingStatus
from app.services import issue_poller_service
from app.services.encryption_service import decrypt_token

router = APIRouter()


class PollResultResponse(BaseModel):
    """Response model for polling results."""

    success: bool
    issues_found: int
    issues_linked: int
    issues_skipped: int
    prs_checked: int = 0
    prs_with_conflicts: int = 0
    pr_tasks_created: int = 0
    error: str | None = None


class PollAllResultResponse(BaseModel):
    """Response model for polling all workspaces."""

    success: bool
    workspaces_polled: int
    total_issues_linked: int
    total_pr_tasks_created: int = 0
    errors: list[str]


class PollingStatusResponse(BaseModel):
    """Response model for polling status."""

    id: int
    workspace_id: int
    last_poll_time: datetime | None
    total_issues_imported: int
    last_poll_issues_found: int
    last_poll_issues_linked: int
    last_poll_issues_skipped: int
    last_poll_prs_checked: int = 0
    last_poll_prs_with_conflicts: int = 0
    total_pr_tasks_created: int = 0
    last_poll_status: str  # "success", "error", "never"
    last_poll_error: str | None
    updated_at: datetime

    class Config:
        from_attributes = True


@router.post(
    "/{workspace_id}/poll-issues",
    response_model=PollResultResponse,
    status_code=status.HTTP_200_OK,
)
def poll_workspace_issues(
    workspace_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Manually trigger polling for new GitHub issues and PRs with 'avery-developer' label.

    This endpoint will:
    1. Fetch all open issues from the workspace's GitHub repository
    2. Filter issues with the 'avery-developer' label
    3. Automatically create task links for issues that aren't already linked
    4. Check PRs with 'avery-developer' label for merge conflicts
    5. Create tasks for PRs with conflicts

    Any workspace member can trigger polling.

    Args:
        workspace_id: Workspace ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        Polling results with counts of found issues, PRs, and created tasks

    Raises:
        HTTPException: If user is not a workspace member or GitHub token is missing
    """
    workspace, _ = get_workspace_or_403(workspace_id, db, current_user)

    # Check if user has GitHub token
    if not current_user.github_token_encrypted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub account not connected. Please connect your GitHub account first.",
        )

    # Decrypt token
    github_token = decrypt_token(current_user.github_token_encrypted)

    # Poll for both issues and PRs
    result = issue_poller_service.poll_workspace_issues_and_prs(
        db, workspace, github_token, label_filter="avery-developer",
        triggered_by=f"user_id:{current_user.id}"
    )

    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result["error"],
        )

    return PollResultResponse(**result)


@router.post(
    "/poll-all-workspaces",
    response_model=PollAllResultResponse,
    status_code=status.HTTP_200_OK,
)
def poll_all_workspaces(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Manually trigger polling for all workspaces (admin only).

    This is primarily for testing and manual triggering.
    In production, this should be restricted to admin users only.

    Args:
        db: Database session
        current_user: Current authenticated user

    Returns:
        Polling results for all workspaces

    Raises:
        HTTPException: If not authorized
    """
    # TODO: Add admin check here
    # For now, any authenticated user can trigger

    result = issue_poller_service.poll_all_workspaces(db)

    return PollAllResultResponse(**result)


@router.get(
    "/{workspace_id}/polling-status",
    response_model=PollingStatusResponse,
    status_code=status.HTTP_200_OK,
)
def get_polling_status(
    workspace_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Get polling status for a workspace.

    Shows the last poll time and cumulative statistics.
    Any workspace member can view polling status.

    Args:
        workspace_id: Workspace ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        Polling status with last poll time and stats

    Raises:
        HTTPException: If user is not a workspace member or status not found
    """
    workspace, _ = get_workspace_or_403(workspace_id, db, current_user)

    # Query polling status
    status_entry = db.query(PollingStatus).filter(
        PollingStatus.workspace_id == workspace_id
    ).first()

    if not status_entry:
        # Return default status if never polled
        return PollingStatusResponse(
            id=0,
            workspace_id=workspace_id,
            last_poll_time=None,
            total_issues_imported=0,
            last_poll_issues_found=0,
            last_poll_issues_linked=0,
            last_poll_issues_skipped=0,
            last_poll_prs_checked=0,
            last_poll_prs_with_conflicts=0,
            total_pr_tasks_created=0,
            last_poll_status="never",
            last_poll_error=None,
            updated_at=datetime.utcnow(),
        )

    return PollingStatusResponse.from_orm(status_entry)
