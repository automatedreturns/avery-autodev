"""Test Run and Test Result API endpoints."""

import logging
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.api.deps import get_current_user
from app.core.permissions import get_workspace_or_403
from app.database import get_db
from app.models.test_result import TestResult
from app.models.test_run import TestRun
from app.models.test_suite import TestSuite
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.test_suite import (
    TestResultListResponse,
    TestResultResponse,
    TestRunCreate,
    TestRunListResponse,
    TestRunResponse,
    TestRunStatusResponse,
)
from app.services.encryption_service import decrypt_token
from app.services.test_execution_service import TestExecutionError, execute_test_suite
from app.services.coverage_service import (
    CoverageParseError,
    get_coverage_diff,
    get_coverage_summary,
    get_uncovered_code_summary,
    parse_coverage_report,
)

router = APIRouter(tags=["test-runs"])


def _execute_test_run_background(
    workspace: Workspace,
    test_suite: TestSuite,
    test_run_id: int,
    github_token: str,
    db_session_maker,
):
    """
    Background task to execute test run.

    Args:
        workspace: Workspace object
        test_suite: Test suite object
        test_run_id: Test run ID
        github_token: GitHub token
        db_session_maker: Database session maker
    """
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        test_run = db.query(TestRun).filter(TestRun.id == test_run_id).first()
        if not test_run:
            return

        execute_test_suite(
            workspace=workspace,
            test_suite=test_suite,
            test_run=test_run,
            github_token=github_token,
            db=db,
        )
    except Exception as e:
        logger.error(f"Background test execution error: {e}")
    finally:
        db.close()


@router.post("/{workspace_id}/test-suites/{suite_id}/run", response_model=TestRunResponse, status_code=status.HTTP_202_ACCEPTED)
def run_test_suite(
    workspace_id: int,
    suite_id: int,
    run_data: TestRunCreate,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Execute all tests in a test suite.

    Runs tests in the background and returns immediately.
    Poll the status endpoint to check progress.

    Args:
        workspace_id: Workspace ID
        suite_id: Test suite ID
        run_data: Test run configuration
        background_tasks: Background tasks handler
        db: Database session
        current_user: Current authenticated user

    Returns:
        Created test run with status 'queued'

    Raises:
        HTTPException: If user lacks permission or suite not found
    """
    workspace, membership = get_workspace_or_403(workspace_id, db, current_user)

    # Verify test suite exists
    test_suite = (
        db.query(TestSuite)
        .filter(TestSuite.id == suite_id, TestSuite.workspace_id == workspace_id)
        .first()
    )

    if not test_suite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test suite not found",
        )

    # Check if user has GitHub token
    if not current_user.github_token_encrypted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub account not connected. Please connect your GitHub account first.",
        )

    # Create test run record - use workspace dev branch if not specified
    branch_name = run_data.branch_name if run_data.branch_name else workspace.github_dev_branch

    test_run = TestRun(
        test_suite_id=suite_id,
        workspace_task_id=run_data.workspace_task_id,
        branch_name=branch_name,
        trigger_type=run_data.trigger_type,
        status="queued",
        triggered_by=current_user.id,
    )
    db.add(test_run)
    db.commit()
    db.refresh(test_run)

    # Decrypt GitHub token
    github_token = decrypt_token(current_user.github_token_encrypted)

    # Execute tests in background
    from app.database import SessionLocal

    background_tasks.add_task(
        _execute_test_run_background,
        workspace=workspace,
        test_suite=test_suite,
        test_run_id=test_run.id,
        github_token=github_token,
        db_session_maker=SessionLocal,
    )

    return TestRunResponse(
        id=test_run.id,
        test_suite_id=test_run.test_suite_id,
        workspace_task_id=test_run.workspace_task_id,
        branch_name=test_run.branch_name,
        trigger_type=test_run.trigger_type,
        status=test_run.status,
        total_tests=test_run.total_tests,
        passed_tests=test_run.passed_tests,
        failed_tests=test_run.failed_tests,
        skipped_tests=test_run.skipped_tests,
        duration_seconds=test_run.duration_seconds,
        coverage_percentage=test_run.coverage_percentage,
        error_message=test_run.error_message,
        started_at=test_run.started_at,
        completed_at=test_run.completed_at,
        triggered_by=test_run.triggered_by,
        created_at=test_run.created_at,
    )


@router.get("/{workspace_id}/test-runs", response_model=TestRunListResponse)
def list_test_runs(
    workspace_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    suite_id: int = None,
    skip: int = 0,
    limit: int = 100,
):
    """
    List test runs in a workspace.

    Args:
        workspace_id: Workspace ID
        db: Database session
        current_user: Current authenticated user
        suite_id: Optional test suite ID to filter by
        skip: Number of records to skip
        limit: Maximum number of records to return

    Returns:
        List of test runs

    Raises:
        HTTPException: If user is not a workspace member
    """
    workspace, membership = get_workspace_or_403(workspace_id, db, current_user)

    # Build query
    query = (
        db.query(TestRun)
        .join(TestSuite)
        .filter(TestSuite.workspace_id == workspace_id)
    )

    if suite_id:
        query = query.filter(TestRun.test_suite_id == suite_id)

    # Get test runs
    test_runs = (
        query
        .order_by(TestRun.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    test_run_responses = [
        TestRunResponse(
            id=tr.id,
            test_suite_id=tr.test_suite_id,
            workspace_task_id=tr.workspace_task_id,
            branch_name=tr.branch_name,
            trigger_type=tr.trigger_type,
            status=tr.status,
            total_tests=tr.total_tests,
            passed_tests=tr.passed_tests,
            failed_tests=tr.failed_tests,
            skipped_tests=tr.skipped_tests,
            duration_seconds=tr.duration_seconds,
            coverage_percentage=tr.coverage_percentage,
            error_message=tr.error_message,
            started_at=tr.started_at,
            completed_at=tr.completed_at,
            triggered_by=tr.triggered_by,
            created_at=tr.created_at,
        )
        for tr in test_runs
    ]

    total = query.count()

    return TestRunListResponse(test_runs=test_run_responses, total=total)


@router.get("/{workspace_id}/test-runs/{run_id}", response_model=TestRunResponse)
def get_test_run(
    workspace_id: int,
    run_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Get detailed test run information.

    Args:
        workspace_id: Workspace ID
        run_id: Test run ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        Test run details

    Raises:
        HTTPException: If user is not a workspace member or run not found
    """
    workspace, membership = get_workspace_or_403(workspace_id, db, current_user)

    test_run = (
        db.query(TestRun)
        .join(TestSuite)
        .filter(TestRun.id == run_id, TestSuite.workspace_id == workspace_id)
        .first()
    )

    if not test_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test run not found",
        )

    return TestRunResponse(
        id=test_run.id,
        test_suite_id=test_run.test_suite_id,
        workspace_task_id=test_run.workspace_task_id,
        branch_name=test_run.branch_name,
        trigger_type=test_run.trigger_type,
        status=test_run.status,
        total_tests=test_run.total_tests,
        passed_tests=test_run.passed_tests,
        failed_tests=test_run.failed_tests,
        skipped_tests=test_run.skipped_tests,
        duration_seconds=test_run.duration_seconds,
        coverage_percentage=test_run.coverage_percentage,
        error_message=test_run.error_message,
        started_at=test_run.started_at,
        completed_at=test_run.completed_at,
        triggered_by=test_run.triggered_by,
        created_at=test_run.created_at,
    )


@router.get("/{workspace_id}/test-runs/{run_id}/status", response_model=TestRunStatusResponse)
def get_test_run_status(
    workspace_id: int,
    run_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Get test run status for polling.

    Lightweight endpoint for checking test execution progress.

    Args:
        workspace_id: Workspace ID
        run_id: Test run ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        Test run status

    Raises:
        HTTPException: If user is not a workspace member or run not found
    """
    workspace, membership = get_workspace_or_403(workspace_id, db, current_user)

    test_run = (
        db.query(TestRun)
        .join(TestSuite)
        .filter(TestRun.id == run_id, TestSuite.workspace_id == workspace_id)
        .first()
    )

    if not test_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test run not found",
        )

    return TestRunStatusResponse(
        id=test_run.id,
        status=test_run.status,
        total_tests=test_run.total_tests,
        passed_tests=test_run.passed_tests,
        failed_tests=test_run.failed_tests,
        skipped_tests=test_run.skipped_tests,
        duration_seconds=test_run.duration_seconds,
        coverage_percentage=test_run.coverage_percentage,
        error_message=test_run.error_message,
        started_at=test_run.started_at,
        completed_at=test_run.completed_at,
    )


@router.get("/{workspace_id}/test-runs/{run_id}/results", response_model=TestResultListResponse)
def get_test_results(
    workspace_id: int,
    run_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    skip: int = 0,
    limit: int = 100,
):
    """
    Get test results for a test run.

    Args:
        workspace_id: Workspace ID
        run_id: Test run ID
        db: Database session
        current_user: Current authenticated user
        skip: Number of records to skip
        limit: Maximum number of records to return

    Returns:
        List of test results

    Raises:
        HTTPException: If user is not a workspace member or run not found
    """
    workspace, membership = get_workspace_or_403(workspace_id, db, current_user)

    # Verify test run exists and belongs to workspace
    test_run = (
        db.query(TestRun)
        .join(TestSuite)
        .filter(TestRun.id == run_id, TestSuite.workspace_id == workspace_id)
        .first()
    )

    if not test_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test run not found",
        )

    # Get test results
    test_results = (
        db.query(TestResult)
        .filter(TestResult.test_run_id == run_id)
        .order_by(TestResult.created_at)
        .offset(skip)
        .limit(limit)
        .all()
    )

    test_result_responses = [
        TestResultResponse(
            id=tr.id,
            test_run_id=tr.test_run_id,
            test_case_id=tr.test_case_id,
            test_name=tr.test_name,
            file_path=tr.file_path,
            status=tr.status,
            duration_seconds=tr.duration_seconds,
            error_message=tr.error_message,
            stack_trace=tr.stack_trace,
            output=tr.output,
            created_at=tr.created_at,
        )
        for tr in test_results
    ]

    total = db.query(TestResult).filter(TestResult.test_run_id == run_id).count()

    return TestResultListResponse(test_results=test_result_responses, total=total)


@router.get("/{workspace_id}/test-suites/{suite_id}/coverage-history")
def get_coverage_history(
    workspace_id: int,
    suite_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int = 10,
):
    """
    Get coverage history for a test suite.

    Returns the last N test runs with coverage data for trend analysis.

    Args:
        workspace_id: Workspace ID
        suite_id: Test suite ID
        db: Database session
        current_user: Current authenticated user
        limit: Number of runs to return

    Returns:
        List of test runs with coverage data

    Raises:
        HTTPException: If user is not a workspace member or suite not found
    """
    workspace, membership = get_workspace_or_403(workspace_id, db, current_user)

    # Verify test suite exists
    test_suite = (
        db.query(TestSuite)
        .filter(TestSuite.id == suite_id, TestSuite.workspace_id == workspace_id)
        .first()
    )

    if not test_suite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test suite not found",
        )

    # Get recent test runs with coverage
    test_runs = (
        db.query(TestRun)
        .filter(
            TestRun.test_suite_id == suite_id,
            TestRun.coverage_percentage.isnot(None),
            TestRun.status == "completed",
        )
        .order_by(TestRun.created_at.desc())
        .limit(limit)
        .all()
    )

    history = [
        {
            "test_run_id": tr.id,
            "coverage_percentage": tr.coverage_percentage,
            "total_tests": tr.total_tests,
            "passed_tests": tr.passed_tests,
            "failed_tests": tr.failed_tests,
            "branch_name": tr.branch_name,
            "created_at": tr.created_at,
        }
        for tr in test_runs
    ]

    return {"history": history, "total": len(history)}
