"""Agent Job Status API endpoints for monitoring Celery task execution."""

from typing import Annotated
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.permissions import get_workspace_or_403
from app.database import get_db
from app.models.user import User
from app.models.agent_job import AgentJob
from pydantic import BaseModel


router = APIRouter()


class AgentJobResponse(BaseModel):
    """Response model for agent job status."""
    id: int
    celery_task_id: str
    workspace_id: int
    task_id: int
    status: str
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    duration: float | None
    retry_count: int
    max_retries: int
    error_message: str | None
    progress_percentage: int
    current_iteration: int | None
    max_iterations: int | None

    class Config:
        from_attributes = True


class AgentJobListResponse(BaseModel):
    """Response model for list of agent jobs."""
    jobs: list[AgentJobResponse]
    total: int


@router.get("/{workspace_id}/tasks/{task_id}/jobs", response_model=AgentJobListResponse)
def list_agent_jobs(
    workspace_id: int,
    task_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    skip: int = 0,
    limit: int = 10,
    status_filter: str = Query(None, description="Filter by status (pending, running, completed, failed)"),
):
    """
    List all agent jobs for a specific workspace task.

    Returns job execution history with status, timing, and error information.

    Args:
        workspace_id: Workspace ID
        task_id: Workspace task ID
        db: Database session
        current_user: Current authenticated user
        skip: Number of records to skip
        limit: Maximum number of records to return
        status_filter: Optional status filter

    Returns:
        List of agent jobs with execution details

    Raises:
        HTTPException: If user lacks permission
    """
    # Verify workspace access
    workspace, _ = get_workspace_or_403(workspace_id, db, current_user)

    # Build query
    query = db.query(AgentJob).filter(
        AgentJob.workspace_id == workspace_id,
        AgentJob.task_id == task_id
    )

    # Apply status filter if provided
    if status_filter:
        query = query.filter(AgentJob.status == status_filter)

    # Get total count
    total = query.count()

    # Get paginated results
    jobs = query.order_by(AgentJob.created_at.desc()).offset(skip).limit(limit).all()

    return AgentJobListResponse(
        jobs=[AgentJobResponse.model_validate(job) for job in jobs],
        total=total
    )


@router.get("/{workspace_id}/tasks/{task_id}/jobs/latest", response_model=AgentJobResponse | None)
def get_latest_agent_job(
    workspace_id: int,
    task_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Get the latest agent job for a workspace task.

    Useful for checking current execution status.

    Args:
        workspace_id: Workspace ID
        task_id: Workspace task ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        Latest agent job or None if no jobs exist

    Raises:
        HTTPException: If user lacks permission
    """
    # Verify workspace access
    workspace, _ = get_workspace_or_403(workspace_id, db, current_user)

    # Get latest job
    job = db.query(AgentJob).filter(
        AgentJob.workspace_id == workspace_id,
        AgentJob.task_id == task_id
    ).order_by(AgentJob.created_at.desc()).first()

    if not job:
        return None

    return AgentJobResponse.model_validate(job)


@router.get("/{workspace_id}/tasks/{task_id}/jobs/{job_id}", response_model=AgentJobResponse)
def get_agent_job(
    workspace_id: int,
    task_id: int,
    job_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Get details of a specific agent job.

    Args:
        workspace_id: Workspace ID
        task_id: Workspace task ID
        job_id: Agent job ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        Agent job details

    Raises:
        HTTPException: If user lacks permission or job not found
    """
    # Verify workspace access
    workspace, _ = get_workspace_or_403(workspace_id, db, current_user)

    # Get job
    job = db.query(AgentJob).filter(
        AgentJob.id == job_id,
        AgentJob.workspace_id == workspace_id,
        AgentJob.task_id == task_id
    ).first()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent job not found"
        )

    return AgentJobResponse.model_validate(job)


@router.get("/{workspace_id}/jobs/stats", response_model=dict)
def get_workspace_job_stats(
    workspace_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    days: int = Query(7, ge=1, le=90, description="Number of days to include in stats"),
):
    """
    Get aggregated statistics for agent jobs in a workspace.

    Returns counts by status, success rate, and average duration.

    Args:
        workspace_id: Workspace ID
        db: Database session
        current_user: Current authenticated user
        days: Number of days to include in stats (default: 7)

    Returns:
        Dictionary with job statistics

    Raises:
        HTTPException: If user lacks permission
    """
    # Verify workspace access
    workspace, _ = get_workspace_or_403(workspace_id, db, current_user)

    # Calculate date range
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    # Get jobs within date range
    jobs = db.query(AgentJob).filter(
        AgentJob.workspace_id == workspace_id,
        AgentJob.created_at >= cutoff_date
    ).all()

    # Calculate statistics
    total_jobs = len(jobs)
    status_counts = {}
    total_duration = 0
    completed_count = 0

    for job in jobs:
        # Count by status
        status_counts[job.status] = status_counts.get(job.status, 0) + 1

        # Calculate average duration for completed jobs
        if job.status in ["completed", "failed"] and job.duration:
            total_duration += job.duration
            completed_count += 1

    avg_duration = total_duration / completed_count if completed_count > 0 else None
    success_rate = (status_counts.get("completed", 0) / total_jobs * 100) if total_jobs > 0 else 0

    return {
        "workspace_id": workspace_id,
        "period_days": days,
        "total_jobs": total_jobs,
        "status_counts": status_counts,
        "success_rate": round(success_rate, 2),
        "average_duration_seconds": round(avg_duration, 2) if avg_duration else None,
    }
