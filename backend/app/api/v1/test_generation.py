"""
Phase 2: Test Generation API endpoints.

Provides endpoints for AI-powered test generation and validation.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.permissions import get_workspace_or_403
from app.database import get_db
from app.models.agent_test_generation import AgentTestGeneration, TestGenerationStatus
from app.models.user import User
from app.schemas.test_generation import (
    AgentTestGenerationCreate,
    AgentTestGenerationResponse,
    AgentTestGenerationUpdate,
    BatchTestGenerationRequest,
    BatchTestGenerationResponse,
    RetryTestGenerationRequest,
    TestGenerationListRequest,
    TestGenerationListResponse,
    TestGenerationRequest,
    TestGenerationStats,
    TestGenerationStatsRequest,
    TestQualityMetrics,
    TestQualityValidationResponse,
)

router = APIRouter(prefix="/test-generation", tags=["test-generation"])


@router.post(
    "",
    response_model=AgentTestGenerationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_test_generation_job(
    generation_request: TestGenerationRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Create a new test generation job and queue it for processing.

    This endpoint creates a job record and immediately queues it for
    background processing using Claude Agent SDK.

    Args:
        generation_request: Test generation request
        db: Database session
        current_user: Current authenticated user

    Returns:
        Created test generation job

    Raises:
        HTTPException: If user is not a workspace member or GitHub token unavailable
    """
    from app.services.github_service import get_github_token_for_workspace
    from app.tasks.test_generation_tasks import process_test_generation_job_task

    # Verify workspace access
    workspace = get_workspace_or_403(generation_request.workspace_id, db, current_user)

    # Get GitHub token for the workspace
    github_token = get_github_token_for_workspace(generation_request.workspace_id, db)
    if not github_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No GitHub token available for this workspace. Please connect your GitHub account.",
        )

    # Create test generation record
    test_gen = AgentTestGeneration(
        workspace_id=generation_request.workspace_id,
        trigger_type=generation_request.trigger_type,
        source_files=generation_request.files,
        generated_test_files=[],
        status=TestGenerationStatus.PENDING.value,
        tests_generated_count=0,
        agent_run_metadata={
            "generation_type": generation_request.generation_type,
            "context": generation_request.context,
            "requested_by": current_user.id,
        },
        validation_passed=False,
    )
    db.add(test_gen)
    db.commit()
    db.refresh(test_gen)

    # Queue the job for background processing
    try:
        process_test_generation_job_task.delay(
            job_id=test_gen.id,
            workspace_id=generation_request.workspace_id,
            github_token=github_token,
        )
        # Update status to indicate it's queued
        test_gen.status = TestGenerationStatus.IN_PROGRESS.value
        db.commit()
    except Exception as e:
        # If queueing fails, keep as pending for later pickup
        import logging
        logging.getLogger(__name__).warning(
            f"Failed to queue test generation job {test_gen.id}: {e}. "
            "Job will be picked up by periodic task."
        )

    return AgentTestGenerationResponse(
        id=test_gen.id,
        workspace_id=test_gen.workspace_id,
        agent_job_id=test_gen.agent_job_id,
        ci_run_id=test_gen.ci_run_id,
        trigger_type=test_gen.trigger_type,
        source_files=test_gen.source_files or [],
        generated_test_files=test_gen.generated_test_files or [],
        status=test_gen.status,
        generation_method=test_gen.generation_method,
        tests_generated_count=test_gen.tests_generated_count or 0,
        tests_passed_count=test_gen.tests_passed_count or 0,
        tests_failed_count=test_gen.tests_failed_count or 0,
        test_quality_score=test_gen.test_quality_score,
        coverage_before=test_gen.coverage_before,
        coverage_after=test_gen.coverage_after,
        coverage_delta=test_gen.coverage_delta,
        validation_passed=test_gen.validation_passed or False,
        validation_errors=test_gen.validation_errors or [],
        prompt_tokens_used=test_gen.prompt_tokens_used or 0,
        completion_tokens_used=test_gen.completion_tokens_used or 0,
        duration_seconds=test_gen.duration_seconds,
        error_message=test_gen.error_message,
        retry_count=test_gen.retry_count or 0,
        max_retries=test_gen.max_retries or 2,
        agent_run_metadata=test_gen.agent_run_metadata,
        created_at=test_gen.created_at,
        updated_at=test_gen.updated_at,
        completed_at=test_gen.completed_at,
    )


@router.get("/{job_id}", response_model=AgentTestGenerationResponse)
def get_test_generation_job(
    job_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Get a specific test generation job.

    Args:
        job_id: Job ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        Test generation job

    Raises:
        HTTPException: If job not found or user lacks access
    """
    job = db.query(AgentTestGeneration).filter(AgentTestGeneration.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test generation job not found",
        )

    # Verify workspace access
    get_workspace_or_403(job.workspace_id, db, current_user)

    return AgentTestGenerationResponse(
        id=job.id,
        workspace_id=job.workspace_id,
        agent_job_id=job.agent_job_id,
        ci_run_id=job.ci_run_id,
        trigger_type=job.trigger_type,
        source_files=job.source_files or [],
        generated_test_files=job.generated_test_files or [],
        status=job.status,
        generation_method=job.generation_method,
        tests_generated_count=job.tests_generated_count or 0,
        tests_passed_count=job.tests_passed_count or 0,
        tests_failed_count=job.tests_failed_count or 0,
        test_quality_score=job.test_quality_score,
        coverage_before=job.coverage_before,
        coverage_after=job.coverage_after,
        coverage_delta=job.coverage_delta,
        validation_passed=job.validation_passed or False,
        validation_errors=job.validation_errors or [],
        prompt_tokens_used=job.prompt_tokens_used or 0,
        completion_tokens_used=job.completion_tokens_used or 0,
        duration_seconds=job.duration_seconds,
        error_message=job.error_message,
        retry_count=job.retry_count or 0,
        max_retries=job.max_retries or 2,
        agent_run_metadata=job.agent_run_metadata,
        created_at=job.created_at,
        updated_at=job.updated_at,
        completed_at=job.completed_at,
    )


@router.get(
    "/workspaces/{workspace_id}/jobs",
    response_model=TestGenerationListResponse,
)
def list_test_generation_jobs(
    workspace_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    status: Optional[str] = Query(None, description="Filter by status"),
    trigger_type: Optional[str] = Query(None, description="Filter by trigger type"),
    limit: int = Query(50, ge=1, le=100, description="Maximum jobs to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """
    List test generation jobs for a workspace.

    Args:
        workspace_id: Workspace ID
        db: Database session
        current_user: Current authenticated user
        status: Optional status filter
        trigger_type: Optional trigger type filter
        limit: Maximum jobs to return
        offset: Offset for pagination

    Returns:
        List of test generation jobs (most recent first)

    Raises:
        HTTPException: If user is not a workspace member
    """
    # Verify workspace access
    get_workspace_or_403(workspace_id, db, current_user)

    # Query jobs
    query = db.query(AgentTestGeneration).filter(AgentTestGeneration.workspace_id == workspace_id)

    if status:
        query = query.filter(AgentTestGeneration.status == status)
    if trigger_type:
        query = query.filter(AgentTestGeneration.trigger_type == trigger_type)

    total = query.count()
    jobs = query.order_by(AgentTestGeneration.created_at.desc()).offset(offset).limit(limit).all()

    return TestGenerationListResponse(
        items=[
            AgentTestGenerationResponse(
                id=j.id,
                workspace_id=j.workspace_id,
                agent_job_id=j.agent_job_id,
                ci_run_id=j.ci_run_id,
                trigger_type=j.trigger_type,
                source_files=j.source_files or [],
                generated_test_files=j.generated_test_files or [],
                status=j.status,
                generation_method=j.generation_method,
                tests_generated_count=j.tests_generated_count or 0,
                tests_passed_count=j.tests_passed_count or 0,
                tests_failed_count=j.tests_failed_count or 0,
                test_quality_score=j.test_quality_score,
                coverage_before=j.coverage_before,
                coverage_after=j.coverage_after,
                coverage_delta=j.coverage_delta,
                validation_passed=j.validation_passed or False,
                validation_errors=j.validation_errors or [],
                prompt_tokens_used=j.prompt_tokens_used or 0,
                completion_tokens_used=j.completion_tokens_used or 0,
                duration_seconds=j.duration_seconds,
                error_message=j.error_message,
                retry_count=j.retry_count or 0,
                max_retries=j.max_retries or 2,
                agent_run_metadata=j.agent_run_metadata,
                created_at=j.created_at,
                updated_at=j.updated_at,
                completed_at=j.completed_at,
            )
            for j in jobs
        ],
        total=total,
        limit=limit,
        offset=offset,
        has_more=(offset + limit) < total,
    )


@router.patch("/{job_id}", response_model=AgentTestGenerationResponse)
def update_test_generation_job(
    job_id: int,
    update_data: AgentTestGenerationUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Update a test generation job.

    Used by agent workflows to update job status and results.

    Args:
        job_id: Job ID
        update_data: Updated job data
        db: Database session
        current_user: Current authenticated user

    Returns:
        Updated test generation job

    Raises:
        HTTPException: If job not found or user lacks access
    """
    job = db.query(AgentTestGeneration).filter(AgentTestGeneration.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test generation job not found",
        )

    # Verify workspace access
    get_workspace_or_403(job.workspace_id, db, current_user)

    # Update fields
    if update_data.status is not None:
        job.status = update_data.status
    if update_data.generated_test_files is not None:
        job.generated_test_files = update_data.generated_test_files
    if update_data.tests_generated_count is not None:
        job.tests_generated_count = update_data.tests_generated_count
    if update_data.test_quality_score is not None:
        job.test_quality_score = update_data.test_quality_score
    if update_data.coverage_delta is not None:
        job.coverage_delta = update_data.coverage_delta
    if update_data.validation_passed is not None:
        job.validation_passed = update_data.validation_passed
    if update_data.error_message is not None:
        job.error_message = update_data.error_message
    if update_data.agent_run_metadata is not None:
        job.agent_run_metadata = update_data.agent_run_metadata
    if update_data.completed_at is not None:
        job.completed_at = update_data.completed_at

    db.commit()
    db.refresh(job)

    return AgentTestGenerationResponse(
        id=job.id,
        workspace_id=job.workspace_id,
        agent_job_id=job.agent_job_id,
        ci_run_id=job.ci_run_id,
        trigger_type=job.trigger_type,
        source_files=job.source_files or [],
        generated_test_files=job.generated_test_files or [],
        status=job.status,
        generation_method=job.generation_method,
        tests_generated_count=job.tests_generated_count or 0,
        tests_passed_count=job.tests_passed_count or 0,
        tests_failed_count=job.tests_failed_count or 0,
        test_quality_score=job.test_quality_score,
        coverage_before=job.coverage_before,
        coverage_after=job.coverage_after,
        coverage_delta=job.coverage_delta,
        validation_passed=job.validation_passed or False,
        validation_errors=job.validation_errors or [],
        prompt_tokens_used=job.prompt_tokens_used or 0,
        completion_tokens_used=job.completion_tokens_used or 0,
        duration_seconds=job.duration_seconds,
        error_message=job.error_message,
        retry_count=job.retry_count or 0,
        max_retries=job.max_retries or 2,
        agent_run_metadata=job.agent_run_metadata,
        created_at=job.created_at,
        updated_at=job.updated_at,
        completed_at=job.completed_at,
    )


@router.post("/{job_id}/retry", response_model=AgentTestGenerationResponse)
def retry_test_generation(
    job_id: int,
    retry_request: RetryTestGenerationRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Retry a failed test generation job.

    Creates a new job with the same configuration as the failed job.

    Args:
        job_id: Original job ID to retry
        retry_request: Retry request (optional context override)
        db: Database session
        current_user: Current authenticated user

    Returns:
        New test generation job

    Raises:
        HTTPException: If job not found, user lacks access, or job didn't fail
    """
    # Get original job
    original_job = db.query(AgentTestGeneration).filter(AgentTestGeneration.id == job_id).first()
    if not original_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test generation job not found",
        )

    # Verify workspace access
    get_workspace_or_403(original_job.workspace_id, db, current_user)

    # Verify job failed
    if original_job.status != TestGenerationStatus.FAILED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only retry failed jobs",
        )

    # Create new job
    new_job = AgentTestGeneration(
        workspace_id=original_job.workspace_id,
        trigger_type=original_job.trigger_type,
        source_files=original_job.source_files,
        generated_test_files=[],
        status=TestGenerationStatus.PENDING.value,
        tests_generated_count=0,
        agent_run_metadata={
            **original_job.agent_run_metadata,
            "retry_of": job_id,
            "retry_context": retry_request.context,
            "retried_by": current_user.id,
        },
        validation_passed=False,
    )
    db.add(new_job)
    db.commit()
    db.refresh(new_job)

    return AgentTestGenerationResponse(
        id=new_job.id,
        workspace_id=new_job.workspace_id,
        agent_job_id=new_job.agent_job_id,
        ci_run_id=new_job.ci_run_id,
        trigger_type=new_job.trigger_type,
        source_files=new_job.source_files or [],
        generated_test_files=new_job.generated_test_files or [],
        status=new_job.status,
        generation_method=new_job.generation_method,
        tests_generated_count=new_job.tests_generated_count or 0,
        tests_passed_count=new_job.tests_passed_count or 0,
        tests_failed_count=new_job.tests_failed_count or 0,
        test_quality_score=new_job.test_quality_score,
        coverage_before=new_job.coverage_before,
        coverage_after=new_job.coverage_after,
        coverage_delta=new_job.coverage_delta,
        validation_passed=new_job.validation_passed or False,
        validation_errors=new_job.validation_errors or [],
        prompt_tokens_used=new_job.prompt_tokens_used or 0,
        completion_tokens_used=new_job.completion_tokens_used or 0,
        duration_seconds=new_job.duration_seconds,
        error_message=new_job.error_message,
        retry_count=new_job.retry_count or 0,
        max_retries=new_job.max_retries or 2,
        agent_run_metadata=new_job.agent_run_metadata,
        created_at=new_job.created_at,
        updated_at=new_job.updated_at,
        completed_at=new_job.completed_at,
    )


@router.post("/batch", response_model=BatchTestGenerationResponse)
def create_batch_test_generation(
    batch_request: BatchTestGenerationRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Create multiple test generation jobs in a batch.

    Useful for generating tests for multiple files at once.

    Args:
        batch_request: Batch test generation request
        db: Database session
        current_user: Current authenticated user

    Returns:
        Batch generation response with job IDs

    Raises:
        HTTPException: If user is not a workspace member
    """
    # Verify workspace access
    get_workspace_or_403(batch_request.workspace_id, db, current_user)

    # Create jobs for each request
    job_ids = []
    for request in batch_request.requests:
        test_gen = AgentTestGeneration(
            workspace_id=batch_request.workspace_id,
            trigger_type=request.trigger_type,
            source_files=request.files,
            generated_test_files=[],
            status=TestGenerationStatus.PENDING.value,
            tests_generated_count=0,
            agent_run_metadata={
                "generation_type": request.generation_type,
                "context": request.context,
                "requested_by": current_user.id,
                "batch_id": batch_request.workspace_id,
            },
            validation_passed=False,
        )
        db.add(test_gen)
        db.flush()  # Get ID
        job_ids.append(test_gen.id)

    db.commit()

    return BatchTestGenerationResponse(
        workspace_id=batch_request.workspace_id,
        job_ids=job_ids,
        total_jobs=len(job_ids),
    )


@router.post("/stats", response_model=TestGenerationStats)
def get_test_generation_stats(
    stats_request: TestGenerationStatsRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Get test generation statistics for a workspace.

    Args:
        stats_request: Stats request
        db: Database session
        current_user: Current authenticated user

    Returns:
        Test generation statistics

    Raises:
        HTTPException: If user is not a workspace member
    """
    # Verify workspace access
    get_workspace_or_403(stats_request.workspace_id, db, current_user)

    # Query jobs
    query = db.query(AgentTestGeneration).filter(
        AgentTestGeneration.workspace_id == stats_request.workspace_id
    )

    if stats_request.days:
        from datetime import datetime, timedelta

        cutoff = datetime.utcnow() - timedelta(days=stats_request.days)
        query = query.filter(AgentTestGeneration.created_at >= cutoff)

    jobs = query.all()

    # Calculate stats
    total_jobs = len(jobs)
    completed_jobs = sum(1 for j in jobs if j.status == TestGenerationStatus.COMPLETED.value)
    failed_jobs = sum(1 for j in jobs if j.status == TestGenerationStatus.FAILED.value)
    pending_jobs = sum(1 for j in jobs if j.status == TestGenerationStatus.PENDING.value)
    in_progress_jobs = sum(1 for j in jobs if j.status == TestGenerationStatus.IN_PROGRESS.value)

    total_tests_generated = sum(j.tests_generated_count for j in jobs if j.tests_generated_count)
    avg_quality_score = (
        sum(j.test_quality_score for j in jobs if j.test_quality_score) / completed_jobs
        if completed_jobs > 0
        else 0.0
    )
    avg_coverage_delta = (
        sum(j.coverage_delta for j in jobs if j.coverage_delta) / completed_jobs
        if completed_jobs > 0
        else 0.0
    )

    return TestGenerationStats(
        workspace_id=stats_request.workspace_id,
        total_jobs=total_jobs,
        completed_jobs=completed_jobs,
        failed_jobs=failed_jobs,
        pending_jobs=pending_jobs,
        in_progress_jobs=in_progress_jobs,
        total_tests_generated=total_tests_generated,
        avg_quality_score=round(avg_quality_score, 2),
        avg_coverage_delta=round(avg_coverage_delta, 2),
    )


@router.post("/{job_id}/validate", response_model=TestQualityValidationResponse)
def validate_test_quality(
    job_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Validate the quality of generated tests.

    Placeholder endpoint - actual validation logic will be implemented in Week 2.

    Args:
        job_id: Job ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        Test quality validation results

    Raises:
        HTTPException: If job not found or user lacks access
    """
    job = db.query(AgentTestGeneration).filter(AgentTestGeneration.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test generation job not found",
        )

    # Verify workspace access
    get_workspace_or_403(job.workspace_id, db, current_user)

    # Verify job is completed
    if job.status != TestGenerationStatus.COMPLETED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only validate completed jobs",
        )

    # TODO: Implement actual validation logic in Week 2
    # For now, return the stored quality score

    quality_score = job.test_quality_score or 0.0
    threshold = 70.0  # Default threshold

    return TestQualityValidationResponse(
        quality_score=quality_score,
        metrics=TestQualityMetrics(
            has_assertions=True,
            assertion_count=0,
            has_edge_cases=False,
            edge_case_count=0,
            has_mocking=False,
            mock_count=0,
            has_error_handling=False,
            error_case_count=0,
            line_count=0,
        ),
        passed=quality_score >= threshold,
        threshold=threshold,
        suggestions=[
            "Implement actual test quality validation in Week 2",
            "Add assertion counting",
            "Detect edge case coverage",
            "Identify mocking usage",
            "Check error handling",
        ],
    )
