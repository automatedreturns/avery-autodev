"""
Phase 2: Coverage Analysis API endpoints.

Provides endpoints for coverage tracking, analysis, delta calculation, and trend analysis.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.permissions import get_workspace_or_403
from app.database import get_db
from app.models.coverage_snapshot import CoverageSnapshot
from app.models.user import User
from app.schemas.coverage import (
    CoverageDeltaRequest,
    CoverageDeltaResponse,
    CoverageReportParseResponse,
    CoverageSnapshotCreate,
    CoverageSnapshotResponse,
    CoverageTrendRequest,
    CoverageTrendResponse,
    FileCoverageChange,
    SnapshotComparisonRequest,
    SnapshotComparisonResponse,
    UncoveredCodeRequest,
    UncoveredCodeResponse,
    UncoveredFileDetail,
)
from app.schemas.test_policy import (
    PolicyDecisionResponse,
    PolicyEnforcementRequest,
    PolicyRecommendationResponse,
    PolicyRecommendationsResponse,
    PolicyViolationResponse,
)
from app.services.test_coverage_analyzer import TestCoverageAnalyzer
from app.services.test_policy_enforcer import TestPolicyEnforcer

router = APIRouter(prefix="/coverage", tags=["coverage"])


@router.post(
    "/snapshots",
    response_model=CoverageSnapshotResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_coverage_snapshot(
    snapshot_data: CoverageSnapshotCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Create a new coverage snapshot.

    Validates that user is a member of the workspace.

    Args:
        snapshot_data: Coverage snapshot data
        db: Database session
        current_user: Current authenticated user

    Returns:
        Created coverage snapshot

    Raises:
        HTTPException: If user is not a workspace member or validation fails
    """
    # Verify workspace access
    get_workspace_or_403(snapshot_data.workspace_id, db, current_user)

    # Create analyzer
    analyzer = TestCoverageAnalyzer(db)

    # Store snapshot
    snapshot = analyzer.store_coverage_snapshot(
        workspace_id=snapshot_data.workspace_id,
        coverage_percent=snapshot_data.coverage_percent,
        lines_covered=snapshot_data.lines_covered,
        lines_total=snapshot_data.lines_total,
        branches_covered=snapshot_data.branches_covered,
        branches_total=snapshot_data.branches_total,
        branch_coverage_percent=snapshot_data.branch_coverage_percent,
        file_coverage=snapshot_data.file_coverage,
        uncovered_lines=snapshot_data.uncovered_lines,
        uncovered_functions=snapshot_data.uncovered_functions,
        commit_sha=snapshot_data.commit_sha,
        branch_name=snapshot_data.branch_name,
        pr_number=snapshot_data.pr_number,
        report_format=snapshot_data.report_format,
        report_path=snapshot_data.report_path,
        ci_run_id=snapshot_data.ci_run_id,
        agent_test_generation_id=snapshot_data.agent_test_generation_id,
    )

    return CoverageSnapshotResponse(
        id=snapshot.id,
        workspace_id=snapshot.workspace_id,
        lines_covered=snapshot.lines_covered,
        lines_total=snapshot.lines_total,
        coverage_percent=snapshot.coverage_percent,
        branches_covered=snapshot.branches_covered,
        branches_total=snapshot.branches_total,
        branch_coverage_percent=snapshot.branch_coverage_percent,
        file_coverage=snapshot.file_coverage,
        uncovered_lines=snapshot.uncovered_lines,
        uncovered_functions=snapshot.uncovered_functions,
        commit_sha=snapshot.commit_sha,
        branch_name=snapshot.branch_name,
        pr_number=snapshot.pr_number,
        report_format=snapshot.report_format,
        report_path=snapshot.report_path,
        ci_run_id=snapshot.ci_run_id,
        agent_test_generation_id=snapshot.agent_test_generation_id,
        created_at=snapshot.created_at,
        coverage_grade=snapshot.coverage_grade,
    )


@router.get(
    "/snapshots/{snapshot_id}",
    response_model=CoverageSnapshotResponse,
)
def get_coverage_snapshot(
    snapshot_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Get a specific coverage snapshot.

    Args:
        snapshot_id: Snapshot ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        Coverage snapshot

    Raises:
        HTTPException: If snapshot not found or user lacks access
    """
    snapshot = db.query(CoverageSnapshot).filter(CoverageSnapshot.id == snapshot_id).first()
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Coverage snapshot not found",
        )

    # Verify workspace access
    get_workspace_or_403(snapshot.workspace_id, db, current_user)

    return CoverageSnapshotResponse(
        id=snapshot.id,
        workspace_id=snapshot.workspace_id,
        lines_covered=snapshot.lines_covered,
        lines_total=snapshot.lines_total,
        coverage_percent=snapshot.coverage_percent,
        branches_covered=snapshot.branches_covered,
        branches_total=snapshot.branches_total,
        branch_coverage_percent=snapshot.branch_coverage_percent,
        file_coverage=snapshot.file_coverage,
        uncovered_lines=snapshot.uncovered_lines,
        uncovered_functions=snapshot.uncovered_functions,
        commit_sha=snapshot.commit_sha,
        branch_name=snapshot.branch_name,
        pr_number=snapshot.pr_number,
        report_format=snapshot.report_format,
        report_path=snapshot.report_path,
        ci_run_id=snapshot.ci_run_id,
        agent_test_generation_id=snapshot.agent_test_generation_id,
        created_at=snapshot.created_at,
        coverage_grade=snapshot.coverage_grade,
    )


@router.get(
    "/workspaces/{workspace_id}/snapshots",
    response_model=list[CoverageSnapshotResponse],
)
def list_coverage_snapshots(
    workspace_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    branch_name: Optional[str] = Query(None, description="Filter by branch name"),
    limit: int = Query(50, ge=1, le=100, description="Maximum snapshots to return"),
):
    """
    List coverage snapshots for a workspace.

    Args:
        workspace_id: Workspace ID
        db: Database session
        current_user: Current authenticated user
        branch_name: Optional branch name filter
        limit: Maximum snapshots to return

    Returns:
        List of coverage snapshots (most recent first)

    Raises:
        HTTPException: If user is not a workspace member
    """
    # Verify workspace access
    get_workspace_or_403(workspace_id, db, current_user)

    # Query snapshots
    query = db.query(CoverageSnapshot).filter(CoverageSnapshot.workspace_id == workspace_id)

    if branch_name:
        query = query.filter(CoverageSnapshot.branch_name == branch_name)

    snapshots = query.order_by(CoverageSnapshot.created_at.desc()).limit(limit).all()

    return [
        CoverageSnapshotResponse(
            id=s.id,
            workspace_id=s.workspace_id,
            lines_covered=s.lines_covered,
            lines_total=s.lines_total,
            coverage_percent=s.coverage_percent,
            branches_covered=s.branches_covered,
            branches_total=s.branches_total,
            branch_coverage_percent=s.branch_coverage_percent,
            file_coverage=s.file_coverage,
            uncovered_lines=s.uncovered_lines,
            uncovered_functions=s.uncovered_functions,
            commit_sha=s.commit_sha,
            branch_name=s.branch_name,
            pr_number=s.pr_number,
            report_format=s.report_format,
            report_path=s.report_path,
            ci_run_id=s.ci_run_id,
            agent_test_generation_id=s.agent_test_generation_id,
            created_at=s.created_at,
            coverage_grade=s.coverage_grade,
        )
        for s in snapshots
    ]


@router.post("/delta", response_model=CoverageDeltaResponse)
def calculate_coverage_delta(
    delta_request: CoverageDeltaRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Calculate coverage delta between two snapshots.

    If previous_snapshot_id is not provided, uses the snapshot before current_snapshot_id.

    Args:
        delta_request: Delta calculation request
        db: Database session
        current_user: Current authenticated user

    Returns:
        Coverage delta with improved/regressed files

    Raises:
        HTTPException: If snapshots not found or user lacks access
    """
    # Get current snapshot
    current = (
        db.query(CoverageSnapshot)
        .filter(CoverageSnapshot.id == delta_request.current_snapshot_id)
        .first()
    )
    if not current:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Current snapshot not found",
        )

    # Verify workspace access
    get_workspace_or_403(current.workspace_id, db, current_user)

    # Create analyzer
    analyzer = TestCoverageAnalyzer(db)

    # Calculate delta
    delta = analyzer.calculate_coverage_delta(
        current_snapshot_id=delta_request.current_snapshot_id,
        previous_snapshot_id=delta_request.previous_snapshot_id,
    )

    if not delta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Previous snapshot not found",
        )

    return CoverageDeltaResponse(
        delta_percent=delta.delta_percent,
        delta_lines=delta.delta_lines,
        previous_coverage=delta.previous_coverage,
        current_coverage=delta.current_coverage,
        improved=delta.improved,
        improved_files=[
            FileCoverageChange(
                path=f["path"],
                delta=f["delta"],
                current=f["current"],
                previous=f["previous"],
                status=f["status"],
            )
            for f in delta.improved_files
        ],
        regressed_files=[
            FileCoverageChange(
                path=f["path"],
                delta=f["delta"],
                current=f["current"],
                previous=f["previous"],
                status=f["status"],
            )
            for f in delta.regressed_files
        ],
    )


@router.post("/compare", response_model=SnapshotComparisonResponse)
def compare_snapshots(
    comparison_request: SnapshotComparisonRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Compare two coverage snapshots in detail.

    Args:
        comparison_request: Snapshot comparison request
        db: Database session
        current_user: Current authenticated user

    Returns:
        Detailed snapshot comparison

    Raises:
        HTTPException: If snapshots not found or user lacks access
    """
    # Get both snapshots
    snapshot1 = (
        db.query(CoverageSnapshot)
        .filter(CoverageSnapshot.id == comparison_request.snapshot_id_1)
        .first()
    )
    snapshot2 = (
        db.query(CoverageSnapshot)
        .filter(CoverageSnapshot.id == comparison_request.snapshot_id_2)
        .first()
    )

    if not snapshot1:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot {comparison_request.snapshot_id_1} not found",
        )
    if not snapshot2:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot {comparison_request.snapshot_id_2} not found",
        )

    # Verify workspace access (both must be from same workspace)
    if snapshot1.workspace_id != snapshot2.workspace_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Snapshots must be from the same workspace",
        )

    get_workspace_or_403(snapshot1.workspace_id, db, current_user)

    # Create analyzer
    analyzer = TestCoverageAnalyzer(db)

    # Compare snapshots
    comparison = analyzer.compare_snapshots(
        comparison_request.snapshot_id_1,
        comparison_request.snapshot_id_2,
    )

    if not comparison:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to compare snapshots",
        )

    return SnapshotComparisonResponse(
        snapshot1=comparison["snapshot1"],
        snapshot2=comparison["snapshot2"],
        overall_delta=comparison["overall_delta"],
        lines_delta=comparison["lines_delta"],
        status=comparison["status"],
        file_changes=[
            FileCoverageChange(
                path=f["path"],
                delta=f["delta"],
                current=f["current"],
                previous=f["previous"],
                status=f["status"],
            )
            for f in comparison["file_changes"]
        ],
        total_files_changed=comparison["total_files_changed"],
    )


@router.post("/trend", response_model=CoverageTrendResponse)
def analyze_coverage_trend(
    trend_request: CoverageTrendRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Analyze coverage trend over time.

    Args:
        trend_request: Trend analysis request
        db: Database session
        current_user: Current authenticated user

    Returns:
        Coverage trend analysis

    Raises:
        HTTPException: If user is not a workspace member
    """
    # Verify workspace access
    get_workspace_or_403(trend_request.workspace_id, db, current_user)

    # Create analyzer
    analyzer = TestCoverageAnalyzer(db)

    # Analyze trend
    trend = analyzer.analyze_coverage_trend(
        workspace_id=trend_request.workspace_id,
        days=trend_request.days,
        branch_name=trend_request.branch_name,
    )

    if not trend:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No coverage data found for the specified period",
        )

    return CoverageTrendResponse(
        workspace_id=trend.workspace_id,
        trend_direction=trend.trend_direction,
        average_coverage=trend.average_coverage,
        min_coverage=trend.min_coverage,
        max_coverage=trend.max_coverage,
        total_change=trend.total_change,
        days_tracked=trend.days_tracked,
        snapshots_count=trend.snapshots_count,
        snapshots=[
            CoverageSnapshotResponse(
                id=s.id,
                workspace_id=s.workspace_id,
                lines_covered=s.lines_covered,
                lines_total=s.lines_total,
                coverage_percent=s.coverage_percent,
                branches_covered=s.branches_covered,
                branches_total=s.branches_total,
                branch_coverage_percent=s.branch_coverage_percent,
                file_coverage=s.file_coverage,
                uncovered_lines=s.uncovered_lines,
                uncovered_functions=s.uncovered_functions,
                commit_sha=s.commit_sha,
                branch_name=s.branch_name,
                pr_number=s.pr_number,
                report_format=s.report_format,
                report_path=s.report_path,
                ci_run_id=s.ci_run_id,
                agent_test_generation_id=s.agent_test_generation_id,
                created_at=s.created_at,
                coverage_grade=s.coverage_grade,
            )
            for s in trend.snapshots
        ],
    )


@router.post("/uncovered", response_model=UncoveredCodeResponse)
def identify_uncovered_code(
    uncovered_request: UncoveredCodeRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Identify uncovered code in a snapshot.

    Returns prioritized files for test generation.

    Args:
        uncovered_request: Uncovered code request
        db: Database session
        current_user: Current authenticated user

    Returns:
        Uncovered code analysis with prioritized files

    Raises:
        HTTPException: If snapshot not found or user lacks access
    """
    # Get snapshot
    snapshot = (
        db.query(CoverageSnapshot)
        .filter(CoverageSnapshot.id == uncovered_request.snapshot_id)
        .first()
    )
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Coverage snapshot not found",
        )

    # Verify workspace access
    get_workspace_or_403(snapshot.workspace_id, db, current_user)

    # Create analyzer
    analyzer = TestCoverageAnalyzer(db)

    # Identify uncovered code
    uncovered = analyzer.identify_uncovered_code(
        uncovered_request.snapshot_id,
        max_files=uncovered_request.max_files,
        max_lines_per_file=uncovered_request.max_lines_per_file,
    )

    if not uncovered:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to identify uncovered code",
        )

    return UncoveredCodeResponse(
        snapshot_id=uncovered["snapshot_id"],
        total_uncovered_lines=uncovered["total_uncovered_lines"],
        files_with_gaps=uncovered["files_with_gaps"],
        priority_files=[
            UncoveredFileDetail(
                path=f["path"],
                uncovered_count=f["uncovered_count"],
                uncovered_lines=f["uncovered_lines"],
                coverage=f["coverage"],
                priority_score=f["priority_score"],
            )
            for f in uncovered["priority_files"]
        ],
        coverage_percent=uncovered["coverage_percent"],
        coverage_grade=uncovered["coverage_grade"],
    )


@router.get(
    "/workspaces/{workspace_id}/uncovered-files",
    response_model=UncoveredCodeResponse,
)
def get_workspace_uncovered_files(
    workspace_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    max_files: int = Query(20, ge=1, le=100, description="Maximum files to return"),
    max_lines_per_file: int = Query(
        50, ge=1, le=500, description="Maximum uncovered lines per file"
    ),
):
    """
    Get uncovered files for a workspace.

    Uses the most recent coverage snapshot to identify files with low coverage.
    Returns prioritized files for test generation.

    Args:
        workspace_id: Workspace ID
        db: Database session
        current_user: Current authenticated user
        max_files: Maximum files to return
        max_lines_per_file: Maximum uncovered lines per file

    Returns:
        Uncovered code analysis with prioritized files

    Raises:
        HTTPException: If user is not a workspace member or no coverage data exists
    """
    # Verify workspace access
    get_workspace_or_403(workspace_id, db, current_user)

    # Get the most recent coverage snapshot for this workspace
    latest_snapshot = (
        db.query(CoverageSnapshot)
        .filter(CoverageSnapshot.workspace_id == workspace_id)
        .order_by(CoverageSnapshot.created_at.desc())
        .first()
    )

    if not latest_snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No coverage data found for this workspace. Please run tests with coverage enabled.",
        )

    # Create analyzer
    analyzer = TestCoverageAnalyzer(db)

    # Identify uncovered code
    uncovered = analyzer.identify_uncovered_code(
        latest_snapshot.id,
        max_files=max_files,
        max_lines_per_file=max_lines_per_file,
    )

    if not uncovered:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to identify uncovered code",
        )

    return UncoveredCodeResponse(
        snapshot_id=uncovered["snapshot_id"],
        total_uncovered_lines=uncovered["total_uncovered_lines"],
        files_with_gaps=uncovered["files_with_gaps"],
        priority_files=[
            UncoveredFileDetail(
                path=f["path"],
                uncovered_count=f["uncovered_count"],
                uncovered_lines=f["uncovered_lines"],
                coverage=f["coverage"],
                priority_score=f["priority_score"],
            )
            for f in uncovered["priority_files"]
        ],
        coverage_percent=uncovered["coverage_percent"],
        coverage_grade=uncovered["coverage_grade"],
    )


@router.post("/check-policies", response_model=PolicyDecisionResponse)
def check_policies(
    enforcement_request: PolicyEnforcementRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Check test policies for a coverage snapshot.

    Validates minimum coverage, regression, test quality, and requirements.

    Args:
        enforcement_request: Policy enforcement request
        db: Database session
        current_user: Current authenticated user

    Returns:
        Policy decision with violations and recommendations

    Raises:
        HTTPException: If user is not a workspace member
    """
    # Verify workspace access
    get_workspace_or_403(enforcement_request.workspace_id, db, current_user)

    # Create enforcer
    enforcer = TestPolicyEnforcer(db)

    # Enforce policies
    decision = enforcer.enforce_policies(
        workspace_id=enforcement_request.workspace_id,
        current_snapshot_id=enforcement_request.current_snapshot_id,
        test_generation_id=enforcement_request.test_generation_id,
        change_type=enforcement_request.change_type,
    )

    return PolicyDecisionResponse(
        passed=decision.passed,
        violations=[
            PolicyViolationResponse(
                rule=v.rule,
                severity=v.severity.value,
                message=v.message,
                current_value=v.current_value,
                expected_value=v.expected_value,
                fix_suggestion=v.fix_suggestion,
                affected_files=v.affected_files,
            )
            for v in decision.violations
        ],
        warnings=[
            PolicyViolationResponse(
                rule=v.rule,
                severity=v.severity.value,
                message=v.message,
                current_value=v.current_value,
                expected_value=v.expected_value,
                fix_suggestion=v.fix_suggestion,
                affected_files=v.affected_files,
            )
            for v in decision.warnings
        ],
        info=[
            PolicyViolationResponse(
                rule=v.rule,
                severity=v.severity.value,
                message=v.message,
                current_value=v.current_value,
                expected_value=v.expected_value,
                fix_suggestion=v.fix_suggestion,
                affected_files=v.affected_files,
            )
            for v in decision.info
        ],
        summary=decision.summary,
        coverage_percent=decision.coverage_percent,
        test_quality_score=decision.test_quality_score,
        tests_generated=decision.tests_generated,
    )


@router.get(
    "/snapshots/{snapshot_id}/recommendations",
    response_model=PolicyRecommendationsResponse,
)
def get_policy_recommendations(
    snapshot_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Get policy recommendations for a coverage snapshot.

    Provides actionable suggestions for improving test coverage.

    Args:
        snapshot_id: Snapshot ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        Policy recommendations

    Raises:
        HTTPException: If snapshot not found or user lacks access
    """
    # Get snapshot
    snapshot = db.query(CoverageSnapshot).filter(CoverageSnapshot.id == snapshot_id).first()
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Coverage snapshot not found",
        )

    # Verify workspace access
    get_workspace_or_403(snapshot.workspace_id, db, current_user)

    # Create enforcer
    enforcer = TestPolicyEnforcer(db)

    # Get recommendations
    recommendations = enforcer.get_policy_recommendations(
        workspace_id=snapshot.workspace_id,
        current_snapshot_id=snapshot_id,
    )

    return PolicyRecommendationsResponse(
        workspace_id=snapshot.workspace_id,
        snapshot_id=snapshot_id,
        recommendations=[
            PolicyRecommendationResponse(
                priority=r["priority"],
                type=r["type"],
                title=r["title"],
                description=r["description"],
                action=r["action"],
                file=r.get("file"),
                lines=r.get("lines", []),
            )
            for r in recommendations
        ],
        total_recommendations=len(recommendations),
    )
