"""Test Suite management API endpoints."""

import logging
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.api.deps import get_current_user
from app.core.permissions import get_workspace_or_403, require_workspace_admin
from app.database import get_db
from app.models.test_case import TestCase
from app.models.test_run import TestRun
from app.models.test_suite import TestSuite
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.test_suite import (
    TestAnalysisRequest,
    TestAnalysisResponse,
    TestCaseCreate,
    TestCaseListResponse,
    TestCaseResponse,
    TestCaseUpdate,
    TestCodeGenerateRequest,
    TestGenerationJobResponse,
    TestRunCreate,
    TestRunResponse,
    TestSuiteCreate,
    TestSuiteListResponse,
    TestSuiteResponse,
    TestSuiteUpdate,
)
from app.services.encryption_service import decrypt_token
from app.services.test_analysis_service import (
    TestAnalysisError,
    analyze_repository_for_tests,
    create_test_cases_from_analysis,
)
from app.services.test_discovery_service import (
    TestDiscoveryError,
    discover_existing_tests,
)

router = APIRouter(tags=["test-suites"])


@router.post("/{workspace_id}/test-suites", response_model=TestSuiteResponse, status_code=status.HTTP_201_CREATED)
def create_test_suite(
    workspace_id: int,
    test_suite_data: TestSuiteCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Create a new test suite in a workspace.

    Automatically discovers and imports existing tests from the test directory
    if the user has a GitHub token configured.

    Requires workspace membership (admin or owner preferred).

    Args:
        workspace_id: Workspace ID
        test_suite_data: Test suite creation data
        db: Database session
        current_user: Current authenticated user

    Returns:
        Created test suite

    Raises:
        HTTPException: If user lacks permission
    """
    workspace, membership = get_workspace_or_403(workspace_id, db, current_user)

    # Create test suite
    test_suite = TestSuite(
        workspace_id=workspace_id,
        name=test_suite_data.name,
        description=test_suite_data.description,
        test_framework=test_suite_data.test_framework,
        test_directory=test_suite_data.test_directory,
        coverage_threshold=test_suite_data.coverage_threshold,
        is_active=test_suite_data.is_active,
        created_by=current_user.id,
    )
    db.add(test_suite)
    db.commit()
    db.refresh(test_suite)

    # Auto-discover existing tests if user has GitHub token
    test_case_count = 0
    if current_user.github_token_encrypted:
        try:
            github_token = decrypt_token(current_user.github_token_encrypted)
            discovery_result = discover_existing_tests(
                test_suite=test_suite,
                workspace=workspace,
                github_token=github_token,
                db=db,
            )
            test_case_count = discovery_result.get("imported_count", 0)
            logger.info(f"Auto-discovered {test_case_count} tests for test suite {test_suite.id}")
        except Exception as e:
            # Log error but don't fail test suite creation
            logger.warning(f"Auto-discovery failed for test suite {test_suite.id}: {e}")

    # Build response
    return TestSuiteResponse(
        id=test_suite.id,
        workspace_id=test_suite.workspace_id,
        name=test_suite.name,
        description=test_suite.description,
        test_framework=test_suite.test_framework,
        test_directory=test_suite.test_directory,
        coverage_threshold=test_suite.coverage_threshold,
        is_active=test_suite.is_active,
        created_by=test_suite.created_by,
        created_at=test_suite.created_at,
        updated_at=test_suite.updated_at,
        test_case_count=test_case_count,
        last_run=None,
    )


@router.get("/{workspace_id}/test-suites", response_model=TestSuiteListResponse)
def list_test_suites(
    workspace_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    skip: int = 0,
    limit: int = 100,
):
    """
    List all test suites in a workspace.

    Args:
        workspace_id: Workspace ID
        db: Database session
        current_user: Current authenticated user
        skip: Number of records to skip
        limit: Maximum number of records to return

    Returns:
        List of test suites

    Raises:
        HTTPException: If user is not a workspace member
    """
    workspace, membership = get_workspace_or_403(workspace_id, db, current_user)

    # Get test suites with count of test cases
    test_suites = (
        db.query(TestSuite)
        .filter(TestSuite.workspace_id == workspace_id)
        .offset(skip)
        .limit(limit)
        .all()
    )

    test_suite_responses = []
    for suite in test_suites:
        test_case_count = db.query(TestCase).filter(TestCase.test_suite_id == suite.id).count()

        # Get last test run
        last_run = (
            db.query(TestRun)
            .filter(TestRun.test_suite_id == suite.id)
            .order_by(TestRun.created_at.desc())
            .first()
        )

        test_suite_responses.append(
            TestSuiteResponse(
                id=suite.id,
                workspace_id=suite.workspace_id,
                name=suite.name,
                description=suite.description,
                test_framework=suite.test_framework,
                test_directory=suite.test_directory,
                coverage_threshold=suite.coverage_threshold,
                is_active=suite.is_active,
                created_by=suite.created_by,
                created_at=suite.created_at,
                updated_at=suite.updated_at,
                test_case_count=test_case_count,
                last_run=last_run.created_at if last_run else None,
            )
        )

    total = db.query(TestSuite).filter(TestSuite.workspace_id == workspace_id).count()

    return TestSuiteListResponse(test_suites=test_suite_responses, total=total)


@router.get("/{workspace_id}/test-suites/{suite_id}", response_model=TestSuiteResponse)
def get_test_suite(
    workspace_id: int,
    suite_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Get detailed test suite information.

    Args:
        workspace_id: Workspace ID
        suite_id: Test suite ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        Test suite details

    Raises:
        HTTPException: If user is not a workspace member or suite not found
    """
    workspace, membership = get_workspace_or_403(workspace_id, db, current_user)

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

    test_case_count = db.query(TestCase).filter(TestCase.test_suite_id == suite_id).count()

    last_run = (
        db.query(TestRun)
        .filter(TestRun.test_suite_id == suite_id)
        .order_by(TestRun.created_at.desc())
        .first()
    )

    return TestSuiteResponse(
        id=test_suite.id,
        workspace_id=test_suite.workspace_id,
        name=test_suite.name,
        description=test_suite.description,
        test_framework=test_suite.test_framework,
        test_directory=test_suite.test_directory,
        coverage_threshold=test_suite.coverage_threshold,
        is_active=test_suite.is_active,
        created_by=test_suite.created_by,
        created_at=test_suite.created_at,
        updated_at=test_suite.updated_at,
        test_case_count=test_case_count,
        last_run=last_run.created_at if last_run else None,
    )


@router.put("/{workspace_id}/test-suites/{suite_id}", response_model=TestSuiteResponse)
def update_test_suite(
    workspace_id: int,
    suite_id: int,
    test_suite_data: TestSuiteUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Update test suite details.

    Requires admin or owner permission.

    Args:
        workspace_id: Workspace ID
        suite_id: Test suite ID
        test_suite_data: Updated test suite data
        db: Database session
        current_user: Current authenticated user

    Returns:
        Updated test suite

    Raises:
        HTTPException: If user lacks permission or suite not found
    """
    workspace, membership = require_workspace_admin(workspace_id, db, current_user)

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

    # Update fields
    if test_suite_data.name is not None:
        test_suite.name = test_suite_data.name
    if test_suite_data.description is not None:
        test_suite.description = test_suite_data.description
    if test_suite_data.test_framework is not None:
        test_suite.test_framework = test_suite_data.test_framework
    if test_suite_data.test_directory is not None:
        test_suite.test_directory = test_suite_data.test_directory
    if test_suite_data.coverage_threshold is not None:
        test_suite.coverage_threshold = test_suite_data.coverage_threshold
    if test_suite_data.is_active is not None:
        test_suite.is_active = test_suite_data.is_active

    db.commit()
    db.refresh(test_suite)

    return get_test_suite(workspace_id, suite_id, db, current_user)


@router.delete("/{workspace_id}/test-suites/{suite_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_test_suite(
    workspace_id: int,
    suite_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Delete test suite.

    Requires admin or owner permission.
    Cascades to all test cases, runs, and results.

    Args:
        workspace_id: Workspace ID
        suite_id: Test suite ID
        db: Database session
        current_user: Current authenticated user

    Raises:
        HTTPException: If user lacks permission or suite not found
    """
    workspace, membership = require_workspace_admin(workspace_id, db, current_user)

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

    db.delete(test_suite)
    db.commit()


# Test Case endpoints
@router.post("/{workspace_id}/test-suites/{suite_id}/test-cases", response_model=TestCaseResponse, status_code=status.HTTP_201_CREATED)
def create_test_case(
    workspace_id: int,
    suite_id: int,
    test_case_data: TestCaseCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Create a new test case in a test suite.

    Args:
        workspace_id: Workspace ID
        suite_id: Test suite ID
        test_case_data: Test case creation data
        db: Database session
        current_user: Current authenticated user

    Returns:
        Created test case

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

    # Create test case
    test_case = TestCase(
        test_suite_id=suite_id,
        file_path=test_case_data.file_path,
        test_name=test_case_data.test_name,
        test_type=test_case_data.test_type,
        description=test_case_data.description,
        mock_data=test_case_data.mock_data,
        assertions=test_case_data.assertions,
        status=test_case_data.status,
    )
    db.add(test_case)
    db.commit()
    db.refresh(test_case)

    return TestCaseResponse(
        id=test_case.id,
        test_suite_id=test_case.test_suite_id,
        file_path=test_case.file_path,
        test_name=test_case.test_name,
        test_type=test_case.test_type,
        description=test_case.description,
        mock_data=test_case.mock_data,
        assertions=test_case.assertions,
        status=test_case.status,
        created_at=test_case.created_at,
        updated_at=test_case.updated_at,
    )


@router.get("/{workspace_id}/test-suites/{suite_id}/test-cases", response_model=TestCaseListResponse)
def list_test_cases(
    workspace_id: int,
    suite_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    skip: int = 0,
    limit: int = 100,
):
    """
    List all test cases in a test suite.

    Args:
        workspace_id: Workspace ID
        suite_id: Test suite ID
        db: Database session
        current_user: Current authenticated user
        skip: Number of records to skip
        limit: Maximum number of records to return

    Returns:
        List of test cases

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

    # Get test cases
    test_cases = (
        db.query(TestCase)
        .filter(TestCase.test_suite_id == suite_id)
        .offset(skip)
        .limit(limit)
        .all()
    )

    test_case_responses = [
        TestCaseResponse(
            id=tc.id,
            test_suite_id=tc.test_suite_id,
            file_path=tc.file_path,
            test_name=tc.test_name,
            test_type=tc.test_type,
            description=tc.description,
            mock_data=tc.mock_data,
            assertions=tc.assertions,
            status=tc.status,
            created_at=tc.created_at,
            updated_at=tc.updated_at,
        )
        for tc in test_cases
    ]

    total = db.query(TestCase).filter(TestCase.test_suite_id == suite_id).count()

    return TestCaseListResponse(test_cases=test_case_responses, total=total)


@router.put("/{workspace_id}/test-suites/{suite_id}/test-cases/{case_id}", response_model=TestCaseResponse)
def update_test_case(
    workspace_id: int,
    suite_id: int,
    case_id: int,
    test_case_data: TestCaseUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Update test case details.

    Args:
        workspace_id: Workspace ID
        suite_id: Test suite ID
        case_id: Test case ID
        test_case_data: Updated test case data
        db: Database session
        current_user: Current authenticated user

    Returns:
        Updated test case

    Raises:
        HTTPException: If user lacks permission or case not found
    """
    workspace, membership = get_workspace_or_403(workspace_id, db, current_user)

    # Verify test suite and test case exist
    test_case = (
        db.query(TestCase)
        .join(TestSuite)
        .filter(
            TestCase.id == case_id,
            TestCase.test_suite_id == suite_id,
            TestSuite.workspace_id == workspace_id,
        )
        .first()
    )

    if not test_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test case not found",
        )

    # Update fields
    if test_case_data.file_path is not None:
        test_case.file_path = test_case_data.file_path
    if test_case_data.test_name is not None:
        test_case.test_name = test_case_data.test_name
    if test_case_data.test_type is not None:
        test_case.test_type = test_case_data.test_type
    if test_case_data.description is not None:
        test_case.description = test_case_data.description
    if test_case_data.mock_data is not None:
        test_case.mock_data = test_case_data.mock_data
    if test_case_data.assertions is not None:
        test_case.assertions = test_case_data.assertions
    if test_case_data.status is not None:
        test_case.status = test_case_data.status

    db.commit()
    db.refresh(test_case)

    return TestCaseResponse(
        id=test_case.id,
        test_suite_id=test_case.test_suite_id,
        file_path=test_case.file_path,
        test_name=test_case.test_name,
        test_type=test_case.test_type,
        description=test_case.description,
        mock_data=test_case.mock_data,
        assertions=test_case.assertions,
        status=test_case.status,
        created_at=test_case.created_at,
        updated_at=test_case.updated_at,
    )


@router.delete("/{workspace_id}/test-suites/{suite_id}/test-cases/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_test_case(
    workspace_id: int,
    suite_id: int,
    case_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Delete test case.

    Args:
        workspace_id: Workspace ID
        suite_id: Test suite ID
        case_id: Test case ID
        db: Database session
        current_user: Current authenticated user

    Raises:
        HTTPException: If user lacks permission or case not found
    """
    workspace, membership = get_workspace_or_403(workspace_id, db, current_user)

    # Verify test suite and test case exist
    test_case = (
        db.query(TestCase)
        .join(TestSuite)
        .filter(
            TestCase.id == case_id,
            TestCase.test_suite_id == suite_id,
            TestSuite.workspace_id == workspace_id,
        )
        .first()
    )

    if not test_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test case not found",
        )

    db.delete(test_case)
    db.commit()


# Test Analysis endpoint
@router.post("/{workspace_id}/test-suites/{suite_id}/analyze", response_model=TestAnalysisResponse)
def analyze_tests(
    workspace_id: int,
    suite_id: int,
    analysis_request: TestAnalysisRequest,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Analyze repository code and generate test case suggestions using AI.

    Uses Claude to analyze source code and suggest comprehensive test cases.

    Args:
        workspace_id: Workspace ID
        suite_id: Test suite ID
        analysis_request: Analysis configuration
        background_tasks: Background tasks handler
        db: Database session
        current_user: Current authenticated user

    Returns:
        Analysis results with suggested test cases

    Raises:
        HTTPException: If user lacks permission, suite not found, or analysis fails
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

    # Decrypt GitHub token
    github_token = decrypt_token(current_user.github_token_encrypted)

    # Perform analysis
    try:
        analysis_result = analyze_repository_for_tests(
            workspace=workspace,
            test_suite=test_suite,
            github_token=github_token,
            db=db,
            file_paths=analysis_request.file_paths,
            focus_areas=analysis_request.focus_areas,
        )

        return TestAnalysisResponse(
            analysis_summary=analysis_result.get("analysis_summary", ""),
            suggested_tests=analysis_result.get("suggested_tests", []),
            coverage_gaps=analysis_result.get("coverage_gaps", []),
            recommendations=analysis_result.get("recommendations", []),
        )

    except TestAnalysisError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/{workspace_id}/test-suites/{suite_id}/apply-suggestions", response_model=TestCaseListResponse)
def apply_test_suggestions(
    workspace_id: int,
    suite_id: int,
    suggested_tests: list[dict],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Create test cases from AI suggestions.

    Args:
        workspace_id: Workspace ID
        suite_id: Test suite ID
        suggested_tests: List of suggested test case dictionaries from analysis
        db: Database session
        current_user: Current authenticated user

    Returns:
        List of created test cases

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

    # Create test cases
    created_cases = create_test_cases_from_analysis(
        test_suite_id=suite_id,
        suggested_tests=suggested_tests,
        db=db,
    )

    test_case_responses = [
        TestCaseResponse(
            id=tc.id,
            test_suite_id=tc.test_suite_id,
            file_path=tc.file_path,
            test_name=tc.test_name,
            test_type=tc.test_type,
            description=tc.description,
            mock_data=tc.mock_data,
            assertions=tc.assertions,
            status=tc.status,
            created_at=tc.created_at,
            updated_at=tc.updated_at,
        )
        for tc in created_cases
    ]

    return TestCaseListResponse(test_cases=test_case_responses, total=len(test_case_responses))


@router.post("/{workspace_id}/test-suites/{suite_id}/discover-tests")
def discover_test_cases(
    workspace_id: int,
    suite_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Discover and import existing tests from the test directory.

    Scans the repository test directory for existing test files and automatically
    imports them as test cases. Supports pytest, Jest, Mocha, and JUnit frameworks.

    Args:
        workspace_id: Workspace ID
        suite_id: Test suite ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        Discovery results with counts of discovered, imported, and skipped tests

    Raises:
        HTTPException: If user lacks permission, suite not found, or discovery fails
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

    # Decrypt GitHub token
    github_token = decrypt_token(current_user.github_token_encrypted)

    # Perform discovery
    try:
        result = discover_existing_tests(
            test_suite=test_suite,
            workspace=workspace,
            github_token=github_token,
            db=db,
        )

        return result

    except TestDiscoveryError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/{workspace_id}/test-suites/{suite_id}/generate-code", response_model=TestGenerationJobResponse)
def generate_test_code(
    workspace_id: int,
    suite_id: int,
    request: TestCodeGenerateRequest,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Start test code generation job in background.

    Creates a job to generate test files, commit them to a new branch, and push to GitHub.
    Returns immediately with a job ID that can be polled for progress.

    Args:
        workspace_id: Workspace ID
        suite_id: Test suite ID
        request: Request body with optional test_case_ids
        background_tasks: FastAPI background tasks
        db: Database session
        current_user: Current authenticated user

    Returns:
        TestGenerationJobResponse with job ID and initial status

    Raises:
        HTTPException: If user lacks permission, suite not found, or validation fails
    """
    from datetime import datetime
    from app.models.test_generation_job import TestGenerationJob

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

    # Get test case count
    query = db.query(TestCase).filter(TestCase.test_suite_id == suite_id)
    if request.test_case_ids:
        query = query.filter(TestCase.id.in_(request.test_case_ids))
    test_case_count = query.count()

    if test_case_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No test cases found to generate",
        )

    # Create job record
    job = TestGenerationJob(
        workspace_id=workspace_id,
        test_suite_id=suite_id,
        created_by=current_user.id,
        status="pending",
        total_tests=test_case_count,
        completed_tests=0,
        current_stage="pending",
        base_branch=workspace.github_dev_branch,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Decrypt GitHub token
    github_token = decrypt_token(current_user.github_token_encrypted)

    # Run generation in background
    background_tasks.add_task(
        _run_test_generation,
        job.id,
        suite_id,
        workspace,
        github_token,
        request.test_case_ids,
    )

    return job


def _run_test_generation(
    job_id: int,
    suite_id: int,
    workspace: Workspace,
    github_token: str,
    test_case_ids: list[int] | None,
):
    """Background task to run test generation."""
    from datetime import datetime
    from app.database import SessionLocal
    from app.models.test_generation_job import TestGenerationJob
    from app.services.test_code_generator_service import (
        TestCodeGeneratorError,
        generate_and_commit_tests,
    )

    db = SessionLocal()
    try:
        # Update job status to running
        job = db.query(TestGenerationJob).filter(TestGenerationJob.id == job_id).first()
        if job:
            job.status = "running"
            job.started_at = datetime.utcnow()
            db.commit()

        # Run generation
        result = generate_and_commit_tests(
            test_suite_id=suite_id,
            workspace=workspace,
            github_token=github_token,
            db=db,
            test_case_ids=test_case_ids,
            job_id=job_id,
        )

        # Update job with results
        job = db.query(TestGenerationJob).filter(TestGenerationJob.id == job_id).first()
        if job:
            job.status = "completed"
            job.completed_at = datetime.utcnow()
            job.branch_name = result["branch_name"]
            job.generated_files = result["generated_files"]
            job.pr_url = f"https://github.com/{workspace.github_repository}/compare/{result['base_branch']}...{result['branch_name']}"
            db.commit()

    except Exception as e:
        # Update job with error
        job = db.query(TestGenerationJob).filter(TestGenerationJob.id == job_id).first()
        if job:
            job.status = "failed"
            job.completed_at = datetime.utcnow()
            job.error_message = str(e)
            db.commit()
    finally:
        db.close()


@router.get("/{workspace_id}/test-generation-jobs/{job_id}", response_model=TestGenerationJobResponse)
def get_test_generation_job(
    workspace_id: int,
    job_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Get test generation job status and progress.

    Args:
        workspace_id: Workspace ID
        job_id: Job ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        TestGenerationJobResponse with current job status and progress

    Raises:
        HTTPException: If user lacks permission or job not found
    """
    from app.models.test_generation_job import TestGenerationJob

    workspace, membership = get_workspace_or_403(workspace_id, db, current_user)

    job = (
        db.query(TestGenerationJob)
        .filter(
            TestGenerationJob.id == job_id,
            TestGenerationJob.workspace_id == workspace_id,
        )
        .first()
    )

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    return job
