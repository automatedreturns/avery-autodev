"""CI Run management and webhook API endpoints."""

import logging
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Header, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.database import get_db
from app.models.agent_job import AgentJob
from app.models.ci_run import CIRun
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.ci_run import (
    CIRunResponse,
    CIRunSummary,
    CIRunUpdate,
    CIWebhookPayload,
    QualityGateResult,
    SelfFixRequest,
    SelfFixResponse,
    IssuePreviewResponse,
    CreateIssueRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ci", tags=["CI Runs"])


def _get_priority_uncovered_files(snapshot, max_files: int = 10) -> list[str]:
    """
    Get files with lowest coverage for test generation priority.

    Args:
        snapshot: CoverageSnapshot object
        max_files: Maximum number of files to return

    Returns:
        List of file paths sorted by coverage (lowest first)
    """
    if not snapshot.file_coverage:
        return []

    # Convert file_coverage dict to list of tuples
    files_with_coverage = []
    for file_path, data in snapshot.file_coverage.items():
        coverage_percent = data.get("lines", 100.0) if isinstance(data, dict) else 100.0
        files_with_coverage.append((file_path, coverage_percent))

    # Sort by coverage (lowest first)
    files_sorted = sorted(files_with_coverage, key=lambda x: x[1])

    # Get files with coverage < 80%
    uncovered = [
        file_path for file_path, coverage in files_sorted[:max_files]
        if coverage < 80.0
    ]

    return uncovered


def verify_webhook_token(authorization: str = Header(None)) -> bool:
    """
    Verify webhook authentication token.

    Args:
        authorization: Authorization header value

    Returns:
        True if token is valid

    Raises:
        HTTPException: If token is invalid or missing
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header is required"
        )

    # Extract token from "Bearer <token>" format
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication scheme. Use 'Bearer <token>'"
            )

        # Verify token matches configured API token
        # In production, you'd use a proper secret management system
        expected_token = getattr(settings, "AVERY_API_TOKEN", None)
        if not expected_token or token != expected_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API token"
            )

        return True
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format"
        )


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def github_actions_webhook(
    payload: CIWebhookPayload,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    authorization: str = Header(None),
):
    """
    Receive GitHub Actions status updates via webhook.

    This endpoint is called by GitHub Actions workflows to report CI status.
    If a CI run fails and hasn't exceeded retry limits, it triggers agent self-fix.

    Args:
        payload: Webhook payload from GitHub Actions
        background_tasks: FastAPI background tasks
        db: Database session
        authorization: Authorization header for webhook authentication

    Returns:
        Success message with CI run ID

    Raises:
        HTTPException: If authentication fails or workspace not found
    """
    # Verify webhook authentication
    verify_webhook_token(authorization)

    pr_info = f"PR #{payload.pr_number}" if payload.pr_number else "push event"
    logger.info(
        f"Received CI webhook for {pr_info}, "
        f"run {payload.run_id}, status: {payload.status}"
    )

    # Find workspace by repository
    workspace = db.query(Workspace).filter(
        Workspace.github_repository == payload.repository
    ).first()

    if not workspace:
        logger.warning(f"Workspace not found for repository: {payload.repository}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workspace not found for repository {payload.repository}"
        )

    # Find or create CI run record
    ci_run = db.query(CIRun).filter(
        CIRun.run_id == payload.run_id,
        CIRun.job_name == payload.job_name
    ).first()

    if not ci_run:
        # Create new CI run
        ci_run = CIRun(
            workspace_id=workspace.id,
            repository=payload.repository,
            pr_number=payload.pr_number,
            branch_name=payload.branch,
            commit_sha=payload.commit_sha,
            run_id=payload.run_id,
            job_name=payload.job_name,
            status=payload.status,
            conclusion=payload.conclusion,
            check_results=payload.check_results
        )
        db.add(ci_run)
        logger.info(f"Created new CI run: {ci_run.id}")
    else:
        # Update existing CI run
        ci_run.update_status(payload.status, payload.conclusion)
        if payload.check_results:
            ci_run.check_results = payload.check_results
        logger.info(f"Updated CI run: {ci_run.id}")

    db.commit()
    db.refresh(ci_run)

    # ============================================================
    # NEW: PROCESS COVERAGE AND ENFORCE TEST POLICIES
    # ============================================================
    policy_check_result = None
    if payload.coverage and payload.status == "completed" and workspace.test_policy_enabled:
        logger.info(
            f"Processing coverage data for CI run {ci_run.id}: "
            f"{payload.coverage.percent}% coverage"
        )

        try:
            from app.services.test_coverage_analyzer import TestCoverageAnalyzer
            from app.services.test_policy_enforcer import TestPolicyEnforcer

            # Transform coverage data to our format
            coverage_data = {
                "coverage_percent": payload.coverage.percent,
                "lines_covered": payload.coverage.lines_covered,
                "lines_total": payload.coverage.lines_total,
                "file_coverage": {},
                "uncovered_lines": {},
                "uncovered_functions": []
            }

            # Parse full coverage JSON if available
            if payload.coverage.coverage_json:
                # Extract file-level coverage if present
                coverage_json = payload.coverage.coverage_json
                if isinstance(coverage_json, dict) and "files" in coverage_json:
                    for file_path, file_data in coverage_json.get("files", {}).items():
                        summary = file_data.get("summary", {})
                        coverage_data["file_coverage"][file_path] = {
                            "lines": summary.get("percent_covered", 0.0),
                            "lines_covered": summary.get("covered_lines", 0),
                            "lines_total": summary.get("num_statements", 0)
                        }
                        # Get missing lines
                        missing_lines = file_data.get("missing_lines", [])
                        if missing_lines:
                            coverage_data["uncovered_lines"][file_path] = missing_lines

            # Create coverage snapshot
            analyzer = TestCoverageAnalyzer(db)
            snapshot = analyzer.create_snapshot(
                workspace_id=workspace.id,
                coverage_data=coverage_data,
                commit_sha=payload.commit_sha,
                branch_name=payload.branch,
                pr_number=payload.pr_number
            )

            logger.info(f"Created coverage snapshot {snapshot.id} for CI run {ci_run.id}")

            # Link snapshot to CI run
            ci_run.coverage_snapshot_id = snapshot.id
            ci_run.coverage_after = payload.coverage.percent

            # Enforce test policies
            enforcer = TestPolicyEnforcer(db)
            policy_decision = enforcer.enforce_policies(
                workspace_id=workspace.id,
                current_snapshot_id=snapshot.id,
                change_type="feature"  # Default to feature for PRs
            )

            # Store policy result
            ci_run.policy_passed = policy_decision.passed
            ci_run.policy_violations = [v.dict() for v in policy_decision.violations]

            logger.info(
                f"Policy check for CI run {ci_run.id}: "
                f"passed={policy_decision.passed}, "
                f"violations={len(policy_decision.violations)}, "
                f"warnings={len(policy_decision.warnings)}"
            )

            policy_check_result = {
                "passed": policy_decision.passed,
                "violations": len(policy_decision.violations),
                "warnings": len(policy_decision.warnings)
            }

            db.commit()

            # ============================================================
            # NEW: AUTO-TRIGGER TEST GENERATION IF POLICY FAILS
            # ============================================================
            if (not policy_decision.passed and
                workspace.test_policy_config.get("auto_generate_tests", False)):

                logger.info(
                    f"Policy failed and auto_generate_tests enabled. "
                    f"Checking if test generation should be triggered..."
                )

                try:
                    # Only trigger for coverage-related violations
                    coverage_violations = [
                        v for v in policy_decision.violations
                        if v.rule in ["minimum_coverage", "coverage_regression"]
                    ]

                    if coverage_violations:
                        # Get files with lowest coverage
                        uncovered_files = _get_priority_uncovered_files(snapshot, max_files=5)

                        if uncovered_files:
                            from app.models.agent_test_generation import AgentTestGeneration

                            # Create test generation job
                            test_gen = AgentTestGeneration(
                                workspace_id=workspace.id,
                                ci_run_id=ci_run.id,
                                trigger_type="auto_policy",
                                source_files=uncovered_files,
                                status="pending",
                                agent_run_metadata={
                                    "triggered_by": "policy_violation",
                                    "coverage_percent": payload.coverage.percent,
                                    "pr_number": payload.pr_number,
                                    "violations": [v.dict() for v in coverage_violations]
                                }
                            )
                            db.add(test_gen)
                            db.commit()

                            logger.info(
                                f"Auto-triggered test generation job {test_gen.id} "
                                f"for {len(uncovered_files)} files: {uncovered_files}"
                            )

                            policy_check_result["test_generation_triggered"] = True
                            policy_check_result["test_generation_job_id"] = test_gen.id

                except Exception as gen_error:
                    logger.error(f"Failed to auto-trigger test generation: {str(gen_error)}")
                    import traceback
                    traceback.print_exc()
                    # Don't fail the webhook if test generation trigger fails
            # ============================================================
            # END OF AUTO-TRIGGER TEST GENERATION
            # ============================================================

        except Exception as e:
            logger.error(f"Error processing coverage for CI run {ci_run.id}: {str(e)}")
            import traceback
            traceback.print_exc()
            # Don't fail the webhook if coverage processing fails
    # ============================================================
    # END OF NEW COVERAGE PROCESSING CODE
    # ============================================================

    # Log CI failure status - self-fix is now triggered manually via "FIX CI" button
    if ci_run.is_failing():
        if ci_run.can_retry():
            logger.info(
                f"CI run {ci_run.id} failed. User can trigger self-fix via 'FIX CI' button "
                f"(retry {ci_run.retry_count}/{ci_run.max_retries})"
            )
        else:
            logger.warning(
                f"CI run {ci_run.id} failed and cannot be retried "
                f"(retry_count: {ci_run.retry_count}, max_retries: {ci_run.max_retries})"
            )

    response_data = {
        "message": "Webhook received successfully",
        "ci_run_id": ci_run.id,
        "status": ci_run.status,
        "conclusion": ci_run.conclusion,
        "can_trigger_self_fix": ci_run.can_retry()
    }

    # Add policy check result to response if available
    if policy_check_result:
        response_data["policy_check"] = policy_check_result

    return response_data


async def trigger_agent_self_fix(ci_run_id: int, workspace_id: int, db: Session):
    """
    Trigger agent to analyze and fix CI failures.

    This function runs in the background after a CI failure is detected.
    It calls the agent service to analyze errors and generate fixes.

    Args:
        ci_run_id: ID of the failed CI run
        workspace_id: ID of the workspace
        db: Database session
    """
    from app.services.ci_self_fix_service import handle_ci_failure

    try:
        ci_run = db.query(CIRun).filter(CIRun.id == ci_run_id).first()
        if not ci_run:
            logger.error(f"CI run {ci_run_id} not found for self-fix")
            return

        logger.info(f"Starting agent self-fix for CI run {ci_run_id}")

        # Call the self-fix service
        result = await handle_ci_failure(ci_run, workspace_id, db)

        logger.info(f"Self-fix completed for CI run {ci_run_id}: {result}")

    except Exception as e:
        logger.error(f"Self-fix failed for CI run {ci_run_id}: {e}", exc_info=True)
        # Update CI run with error
        ci_run = db.query(CIRun).filter(CIRun.id == ci_run_id).first()
        if ci_run:
            ci_run.error_summary = f"Self-fix error: {str(e)}"
            db.commit()


@router.get("/runs/{ci_run_id}", response_model=CIRunResponse)
def get_ci_run(
    ci_run_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Get details of a specific CI run.

    Args:
        ci_run_id: CI run ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        CI run details

    Raises:
        HTTPException: If CI run not found or user lacks permission
    """
    ci_run = db.query(CIRun).filter(CIRun.id == ci_run_id).first()

    if not ci_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CI run {ci_run_id} not found"
        )

    # Check user has access to workspace
    workspace = db.query(Workspace).filter(Workspace.id == ci_run.workspace_id).first()
    if workspace.owner_id != current_user.id:
        # TODO: Check workspace membership
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this CI run"
        )

    return ci_run


@router.get("/workspaces/{workspace_id}/runs", response_model=list[CIRunSummary])
def list_ci_runs(
    workspace_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    pr_number: int = None,
    status: str = None,
    limit: int = 50,
):
    """
    List CI runs for a workspace.

    Args:
        workspace_id: Workspace ID
        db: Database session
        current_user: Current authenticated user
        pr_number: Filter by PR number (optional)
        status: Filter by status (optional)
        limit: Maximum number of results

    Returns:
        List of CI run summaries

    Raises:
        HTTPException: If workspace not found or user lacks permission
    """
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()

    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workspace {workspace_id} not found"
        )

    # Check user has access
    if workspace.owner_id != current_user.id:
        # TODO: Check workspace membership
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this workspace"
        )

    # Build query
    query = db.query(CIRun).filter(CIRun.workspace_id == workspace_id)

    if pr_number:
        query = query.filter(CIRun.pr_number == pr_number)

    if status:
        query = query.filter(CIRun.status == status)

    # Order by most recent first
    query = query.order_by(CIRun.created_at.desc()).limit(limit)

    return query.all()


@router.get("/runs/{ci_run_id}/issue-preview", response_model=IssuePreviewResponse)
async def preview_github_issue(
    ci_run_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Preview the GitHub issue that would be created for a CI run.

    This allows users to review the issue content before creating it.

    Args:
        ci_run_id: CI run ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        Issue preview with title, body, and labels

    Raises:
        HTTPException: If CI run not found or user lacks permission
    """
    from app.services.ci_self_fix_service import analyze_ci_errors, build_issue_content
    from app.services.github_actions_service import GitHubActionsService
    from app.services.encryption_service import decrypt_token

    ci_run = db.query(CIRun).filter(CIRun.id == ci_run_id).first()

    if not ci_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CI run {ci_run_id} not found"
        )

    # Check permission
    workspace = db.query(Workspace).filter(Workspace.id == ci_run.workspace_id).first()
    if workspace.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to view this CI run"
        )

    # Get GitHub token
    if not workspace.owner.github_token_encrypted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub token not configured for this workspace"
        )

    github_token = decrypt_token(workspace.owner.github_token_encrypted)

    # Analyze errors
    gh_actions = GitHubActionsService(github_token)
    error_analysis = analyze_ci_errors(ci_run, gh_actions)

    # Build issue content
    title, body = build_issue_content(
        ci_run=ci_run,
        error_analysis=error_analysis,
        self_fix_error=ci_run.error_summary if ci_run.self_fix_attempted else None
    )

    return IssuePreviewResponse(
        title=title,
        body=body,
        labels=["avery-developer", "ci-failure", "automated"],
        ci_run_id=ci_run.id
    )


@router.post("/runs/{ci_run_id}/create-issue", response_model=SelfFixResponse)
async def create_github_issue_for_ci_run(
    ci_run_id: int,
    request: CreateIssueRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Create a GitHub issue with 'avery-developer' label for a failed CI run.

    The issue will be picked up by the coding agent for automated resolution.
    Users can customize the title and body before creating.

    Args:
        ci_run_id: CI run ID
        request: Issue creation request with title, body, and labels
        db: Database session
        current_user: Current authenticated user

    Returns:
        Response with issue creation status

    Raises:
        HTTPException: If CI run not found or user lacks permission
    """
    from app.services.encryption_service import decrypt_token
    from app.services import github_service

    ci_run = db.query(CIRun).filter(CIRun.id == ci_run_id).first()

    if not ci_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CI run {ci_run_id} not found"
        )

    # Check permission
    workspace = db.query(Workspace).filter(Workspace.id == ci_run.workspace_id).first()
    if workspace.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to create issues for this workspace"
        )

    # Get GitHub token
    if not workspace.owner.github_token_encrypted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub token not configured for this workspace"
        )

    github_token = decrypt_token(workspace.owner.github_token_encrypted)

    # Create the GitHub issue with user-provided content
    try:
        result = github_service.create_issue(
            token=github_token,
            repo=ci_run.repository,
            title=request.title,
            body=request.body,
            labels=request.labels or ["avery-developer", "ci-failure", "automated"]
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create GitHub issue: {result.get('error')}"
            )

        logger.info(
            f"Created GitHub issue #{result['issue_number']} for CI run {ci_run_id}: "
            f"{result['issue_url']}"
        )

        return SelfFixResponse(
            success=True,
            ci_run_id=ci_run.id,
            retry_count=ci_run.retry_count,
            message=f"GitHub issue #{result['issue_number']} created successfully",
            issue_url=result.get("issue_url"),
            issue_number=result.get("issue_number")
        )

    except Exception as e:
        logger.error(f"Failed to create GitHub issue for CI run {ci_run_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create GitHub issue: {str(e)}"
        )


@router.get("/runs/{ci_run_id}/quality-gate", response_model=QualityGateResult)
def evaluate_quality_gate(
    ci_run_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Evaluate quality gate for a CI run.

    Quality gates check:
    - All tests passed
    - No lint errors
    - No type errors
    - Build succeeded
    - Coverage not decreased

    Args:
        ci_run_id: CI run ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        Quality gate evaluation result

    Raises:
        HTTPException: If CI run not found
    """
    from app.services.quality_gate_service import evaluate_quality_gate as evaluate

    ci_run = db.query(CIRun).filter(CIRun.id == ci_run_id).first()

    if not ci_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CI run {ci_run_id} not found"
        )

    # Check permission
    workspace = db.query(Workspace).filter(Workspace.id == ci_run.workspace_id).first()
    if workspace.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this CI run"
        )

    return evaluate(ci_run, db)


@router.post("/runs/{ci_run_id}/self-fix", response_model=SelfFixResponse)
async def trigger_self_fix(
    ci_run_id: int,
    request: SelfFixRequest,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Manually trigger agent self-fix for a failed CI run.

    This endpoint allows users to explicitly trigger the self-fix process
    via the "FIX CI" button in the UI.

    Args:
        ci_run_id: CI run ID
        request: Self-fix request with optional force flag
        background_tasks: FastAPI background tasks
        db: Database session
        current_user: Current authenticated user

    Returns:
        Response indicating self-fix was triggered

    Raises:
        HTTPException: If CI run not found, user lacks permission, or cannot retry
    """
    ci_run = db.query(CIRun).filter(CIRun.id == ci_run_id).first()

    if not ci_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CI run {ci_run_id} not found"
        )

    # Check permission
    workspace = db.query(Workspace).filter(Workspace.id == ci_run.workspace_id).first()
    if workspace.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to trigger self-fix for this workspace"
        )

    # Check if CI run is in a failed state
    if not ci_run.is_failing():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CI run is not in a failed state"
        )

    # Check if can retry (unless force is set)
    if not ci_run.can_retry() and not request.force:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"CI run has reached maximum retry count ({ci_run.retry_count}/{ci_run.max_retries}). "
                   f"Use force=true to override."
        )

    logger.info(
        f"User {current_user.id} triggered self-fix for CI run {ci_run_id} "
        f"(retry {ci_run.retry_count + 1}/{ci_run.max_retries}, force={request.force})"
    )

    # Trigger self-fix in background
    background_tasks.add_task(
        trigger_agent_self_fix,
        ci_run_id=ci_run.id,
        workspace_id=workspace.id,
        db=db
    )

    return SelfFixResponse(
        success=True,
        ci_run_id=ci_run.id,
        retry_count=ci_run.retry_count,
        message=f"Self-fix triggered successfully. Retry {ci_run.retry_count + 1}/{ci_run.max_retries}"
    )
