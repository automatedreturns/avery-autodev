"""Pydantic schemas for CI Run API validation and serialization."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# Base schema with common fields
class CIRunBase(BaseModel):
    """Base CI run schema with common attributes."""

    repository: str = Field(..., pattern=r"^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$")
    pr_number: Optional[int] = Field(None, gt=0)  # Optional for push events
    branch_name: str = Field(..., min_length=1)
    commit_sha: str = Field(..., min_length=7, max_length=40)
    run_id: str = Field(..., min_length=1)
    job_name: str = Field(..., min_length=1)
    workflow_name: str = Field(default="Agent PR Validation")


# Coverage data from GitHub Actions
class CICoverageData(BaseModel):
    """Schema for coverage data from CI."""

    percent: float = Field(..., ge=0, le=100, description="Coverage percentage")
    lines_covered: int = Field(..., ge=0, description="Number of lines covered")
    lines_total: int = Field(..., ge=0, description="Total number of lines")
    coverage_json: Optional[dict[str, Any]] = Field(None, description="Full coverage JSON from pytest/jest")


# Webhook payload from GitHub Actions
class CIWebhookPayload(BaseModel):
    """Schema for incoming webhook from GitHub Actions."""

    pr_number: Optional[int] = Field(None, gt=0, description="Pull request number (null for push events)")
    run_id: str = Field(..., description="GitHub Actions run ID")
    job_name: str = Field(..., description="Job name (e.g., test-backend)")
    status: str = Field(..., description="Job status: queued, in_progress, completed")
    conclusion: Optional[str] = Field(None, description="Job conclusion: success, failure, cancelled, skipped")
    repository: str = Field(..., pattern=r"^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$")
    branch: str = Field(..., description="Branch name")
    commit_sha: str = Field(..., description="Commit SHA")
    check_results: Optional[dict[str, str]] = Field(None, description="Individual check results")
    coverage: Optional[CICoverageData] = Field(None, description="Coverage data from tests")
    workspace_id: int = Field(..., gt=0, description="Workspace ID")


# Schema for creating a CI run manually (if needed)
class CIRunCreate(CIRunBase):
    """Schema for creating a new CI run."""

    workspace_id: int = Field(..., gt=0)
    agent_job_id: Optional[int] = None
    status: str = Field(default="queued")


# Schema for updating a CI run
class CIRunUpdate(BaseModel):
    """Schema for updating a CI run - all fields optional."""

    status: Optional[str] = None
    conclusion: Optional[str] = None
    logs_url: Optional[str] = None
    check_results: Optional[dict[str, Any]] = None
    error_summary: Optional[str] = None
    raw_logs: Optional[str] = None
    coverage_before: Optional[float] = Field(None, ge=0, le=100)
    coverage_after: Optional[float] = Field(None, ge=0, le=100)
    tests_total: Optional[int] = Field(None, ge=0)
    tests_passed: Optional[int] = Field(None, ge=0)
    tests_failed: Optional[int] = Field(None, ge=0)
    tests_skipped: Optional[int] = Field(None, ge=0)
    lint_errors_count: Optional[int] = Field(None, ge=0)
    type_errors_count: Optional[int] = Field(None, ge=0)


# Response schema
class CIRunResponse(CIRunBase):
    """Schema for CI run in responses."""

    id: int
    workspace_id: int
    agent_job_id: Optional[int]
    status: str
    conclusion: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_seconds: Optional[float]
    logs_url: Optional[str]
    check_results: Optional[dict[str, Any]]
    error_summary: Optional[str]
    coverage_before: Optional[float]
    coverage_after: Optional[float]
    coverage_delta: Optional[float]
    retry_count: int
    max_retries: int
    self_fix_attempted: bool
    self_fix_successful: Optional[bool]
    tests_total: Optional[int]
    tests_passed: Optional[int]
    tests_failed: Optional[int]
    tests_skipped: Optional[int]
    lint_errors_count: Optional[int]
    type_errors_count: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Summary response for listing
class CIRunSummary(BaseModel):
    """Schema for CI run summary in list responses."""

    id: int
    pr_number: Optional[int]
    job_name: str
    status: str
    conclusion: Optional[str]
    duration_seconds: Optional[float]
    tests_passed: Optional[int]
    tests_failed: Optional[int]
    coverage_delta: Optional[float]
    self_fix_attempted: bool
    created_at: datetime

    class Config:
        from_attributes = True


# Quality gate result
class QualityGateResult(BaseModel):
    """Schema for quality gate evaluation result."""

    passed: bool
    pr_number: int
    checks: dict[str, bool] = Field(
        description="Individual check results (all_tests_passed, no_lint_errors, etc.)"
    )
    violations: list[str] = Field(
        description="List of quality gate violations"
    )
    coverage_delta: Optional[float]
    recommendation: str = Field(
        description="Recommendation: approve, request_changes, or needs_review"
    )


# Self-fix request
class SelfFixRequest(BaseModel):
    """Schema for requesting agent self-fix."""

    ci_run_id: int = Field(..., gt=0)
    force: bool = Field(default=False, description="Force retry even if max retries reached")


# Self-fix response (now also used for create-issue endpoint)
class SelfFixResponse(BaseModel):
    """Schema for self-fix or issue creation operation response."""

    success: bool
    ci_run_id: int
    retry_count: int
    message: str
    new_commit_sha: Optional[str] = None
    fixes_applied: Optional[list[dict[str, str]]] = None
    issue_url: Optional[str] = None
    issue_number: Optional[int] = None


# Issue preview request/response
class IssuePreviewResponse(BaseModel):
    """Schema for issue preview before creation."""

    title: str
    body: str
    labels: list[str]
    ci_run_id: int


class CreateIssueRequest(BaseModel):
    """Schema for creating issue with custom title/body."""

    title: str
    body: str
    labels: Optional[list[str]] = ["avery-developer", "ci-failure", "automated"]
