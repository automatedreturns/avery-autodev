"""Coder Agent API endpoints for autonomous code generation."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.permissions import get_workspace_or_403
from app.database import get_db
from app.models.user import User
from app.models.workspace_task import WorkspaceTask
from app.schemas.coder_agent import (
    CoderAgentExecuteRequest,
    CoderAgentExecuteResponse,
    CoderAgentStatusResponse,
)
from app.services.coder_agent_service import execute_coder_agent
from app.services.encryption_service import decrypt_token
from app.services.git_providers import get_git_provider_for_workspace

router = APIRouter()


def _execute_agent_background(
    task_id: int,
    workspace_id: int,
    token: str,
    repo: str,
    base_branch: str,
    issue_number: int,
    user_context: str,
    files_to_modify: list[str] | None,
    db: Session,
    git_provider=None,
    user_id: int | None = None,
):
    """
    Background task to execute the coder agent.

    Updates the workspace task status in the database as it progresses.
    """
    # Update status to running
    task = db.query(WorkspaceTask).filter(WorkspaceTask.id == task_id).first()
    if task:
        task.agent_status = "running"
        task.agent_executed_at = datetime.utcnow()
        task.agent_error = None
        task.agent_context = user_context  # Store user context
        db.commit()

    # Execute the agent
    result = execute_coder_agent(
        token=token,
        repo=repo,
        base_branch=base_branch,
        issue_number=issue_number,
        user_context=user_context,
        files_to_modify=files_to_modify,
        git_provider=git_provider,
        user_id=str(user_id) if user_id else None,
        workspace_id=str(workspace_id),
    )

    # Update task with results
    task = db.query(WorkspaceTask).filter(WorkspaceTask.id == task_id).first()
    if task:
        if result["success"]:
            task.agent_status = "completed"
            task.agent_branch_name = result["branch_name"]
            task.agent_pr_number = result["pr_number"]
            task.agent_pr_url = result["pr_url"]
            task.agent_error = None
        else:
            task.agent_status = "failed"
            task.agent_error = result["error"]

        db.commit()


@router.post(
    "/{workspace_id}/tasks/{task_id}/execute-agent",
    response_model=CoderAgentExecuteResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def execute_agent(
    workspace_id: int,
    task_id: int,
    request_data: CoderAgentExecuteRequest,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Execute the coder agent to automatically implement a solution for a task.

    This endpoint starts the agent execution in the background and returns immediately.
    The agent will:
    1. Fetch issue details from GitHub
    2. Analyze the codebase
    3. Generate code using Claude API
    4. Create a new branch
    5. Commit changes
    6. Create a draft pull request

    Poll the agent-status endpoint to check progress.

    Any workspace member can execute the agent.

    Args:
        workspace_id: Workspace ID
        task_id: Task ID to execute agent on
        request_data: Agent execution parameters
        background_tasks: FastAPI background tasks
        db: Database session
        current_user: Current authenticated user

    Returns:
        Execution status with task ID

    Raises:
        HTTPException: If user lacks permission, task not found, or agent already running
    """
    workspace, _ = get_workspace_or_403(workspace_id, db, current_user)

    # Check if user has GitHub token
    if not current_user.github_token_encrypted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub account not connected. Please connect your GitHub account first.",
        )

    # Get the task
    task = (
        db.query(WorkspaceTask)
        .filter(WorkspaceTask.id == task_id, WorkspaceTask.workspace_id == workspace_id)
        .first()
    )

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found in this workspace",
        )

    # Check if agent is already running
    if task.agent_status == "running":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Agent is already running for this task. Please wait for it to complete.",
        )

    # Decrypt GitHub token
    token = decrypt_token(current_user.github_token_encrypted)

    # Determine target branch
    target_branch = request_data.target_branch or workspace.github_dev_branch

    # Start agent execution in background
    git_provider = get_git_provider_for_workspace(workspace)
    background_tasks.add_task(
        _execute_agent_background,
        task_id=task.id,
        workspace_id=workspace_id,
        token=token,
        repo=workspace.github_repository,
        base_branch=target_branch,
        issue_number=task.github_issue_number,
        user_context=request_data.additional_context,
        files_to_modify=request_data.files_to_modify,
        db=db,
        git_provider=git_provider,
        user_id=current_user.id,
    )

    return CoderAgentExecuteResponse(
        status="started",
        message=f"Coder agent execution started for issue #{task.github_issue_number}.",
        task_id=task.id,
    )


@router.get(
    "/{workspace_id}/tasks/{task_id}/agent-status",
    response_model=CoderAgentStatusResponse,
)
def get_agent_status(
    workspace_id: int,
    task_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Get the current status of the coder agent for a task.

    Poll this endpoint to check if the agent has completed execution.

    Any workspace member can check agent status.

    Args:
        workspace_id: Workspace ID
        task_id: Task ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        Current agent status

    Raises:
        HTTPException: If user lacks permission or task not found
    """
    workspace, _ = get_workspace_or_403(workspace_id, db, current_user)

    # Get the task
    task = (
        db.query(WorkspaceTask)
        .filter(WorkspaceTask.id == task_id, WorkspaceTask.workspace_id == workspace_id)
        .first()
    )

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found in this workspace",
        )

    return CoderAgentStatusResponse(
        status=task.agent_status,
        branch_name=task.agent_branch_name,
        pr_number=task.agent_pr_number,
        pr_url=task.agent_pr_url,
        error=task.agent_error,
        executed_at=task.agent_executed_at,
    )
