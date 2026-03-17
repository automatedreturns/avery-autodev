"""Pydantic schemas for Test Suite API."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# Test Suite Schemas
class TestSuiteBase(BaseModel):
    """Base schema for Test Suite."""

    name: str = Field(..., min_length=1, max_length=255, description="Test suite name")
    description: Optional[str] = Field(None, description="Test suite description")
    test_framework: str = Field(..., description="Test framework (pytest, jest, mocha, junit, etc.)")
    test_directory: str = Field(..., description="Relative path to test directory in repository")
    coverage_threshold: float = Field(80.0, ge=0, le=100, description="Minimum coverage percentage")
    is_active: bool = Field(True, description="Whether the test suite is active")


class TestSuiteCreate(TestSuiteBase):
    """Schema for creating a new test suite."""

    pass


class TestSuiteUpdate(BaseModel):
    """Schema for updating a test suite."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    test_framework: Optional[str] = None
    test_directory: Optional[str] = None
    coverage_threshold: Optional[float] = Field(None, ge=0, le=100)
    is_active: Optional[bool] = None


class TestSuiteResponse(TestSuiteBase):
    """Schema for test suite response."""

    id: int
    workspace_id: int
    created_by: int
    created_at: datetime
    updated_at: datetime
    test_case_count: int = Field(0, description="Number of test cases in suite")
    last_run: Optional[datetime] = Field(None, description="Last test run timestamp")

    class Config:
        from_attributes = True


class TestSuiteListResponse(BaseModel):
    """Schema for list of test suites."""

    test_suites: list[TestSuiteResponse]
    total: int


# Test Case Schemas
class TestCaseBase(BaseModel):
    """Base schema for Test Case."""

    file_path: str = Field(..., description="Relative path to test file")
    test_name: str = Field(..., min_length=1, max_length=255, description="Test function/method name")
    test_type: str = Field(..., description="Test type (unit, integration, e2e, performance)")
    description: Optional[str] = Field(None, description="Test description")
    mock_data: Optional[dict[str, Any]] = Field(None, description="Mock data configuration")
    assertions: Optional[dict[str, Any]] = Field(None, description="Expected outcomes and assertions")
    status: str = Field("active", description="Test status (active, disabled, deprecated)")


class TestCaseCreate(TestCaseBase):
    """Schema for creating a new test case."""

    pass


class TestCaseUpdate(BaseModel):
    """Schema for updating a test case."""

    file_path: Optional[str] = None
    test_name: Optional[str] = Field(None, min_length=1, max_length=255)
    test_type: Optional[str] = None
    description: Optional[str] = None
    mock_data: Optional[dict[str, Any]] = None
    assertions: Optional[dict[str, Any]] = None
    status: Optional[str] = None


class TestCaseResponse(TestCaseBase):
    """Schema for test case response."""

    id: int
    test_suite_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TestCaseListResponse(BaseModel):
    """Schema for list of test cases."""

    test_cases: list[TestCaseResponse]
    total: int


# Test Run Schemas
class TestRunCreate(BaseModel):
    """Schema for creating a new test run."""

    branch_name: Optional[str] = Field(None, description="Git branch to run tests on (defaults to workspace dev branch)")
    trigger_type: str = Field("manual", description="Trigger type (manual, auto, pre-pr, scheduled)")
    workspace_task_id: Optional[int] = Field(None, description="Associated workspace task ID")


class TestRunResponse(BaseModel):
    """Schema for test run response."""

    id: int
    test_suite_id: int
    workspace_task_id: Optional[int]
    branch_name: str
    trigger_type: str
    status: str
    total_tests: int
    passed_tests: int
    failed_tests: int
    skipped_tests: int
    duration_seconds: Optional[float]
    coverage_percentage: Optional[float]
    error_message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    triggered_by: int
    created_at: datetime

    class Config:
        from_attributes = True


class TestRunListResponse(BaseModel):
    """Schema for list of test runs."""

    test_runs: list[TestRunResponse]
    total: int


class TestRunStatusResponse(BaseModel):
    """Schema for test run status (for polling)."""

    id: int
    status: str
    total_tests: int
    passed_tests: int
    failed_tests: int
    skipped_tests: int
    duration_seconds: Optional[float]
    coverage_percentage: Optional[float]
    error_message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]


# Test Result Schemas
class TestResultResponse(BaseModel):
    """Schema for test result response."""

    id: int
    test_run_id: int
    test_case_id: Optional[int]
    test_name: str
    file_path: str
    status: str
    duration_seconds: Optional[float]
    error_message: Optional[str]
    stack_trace: Optional[str]
    output: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class TestResultListResponse(BaseModel):
    """Schema for list of test results."""

    test_results: list[TestResultResponse]
    total: int


# Test Analysis Schemas
class TestAnalysisRequest(BaseModel):
    """Schema for requesting test analysis."""

    file_paths: Optional[list[str]] = Field(None, description="Specific files to analyze (null for all)")
    focus_areas: Optional[list[str]] = Field(None, description="Areas to focus on (e.g., ['authentication', 'api'])")


class GeneratedTestCase(BaseModel):
    """Schema for AI-generated test case suggestion."""

    file_path: str
    test_name: str
    test_type: str
    description: str
    mock_data: Optional[dict[str, Any]] = None
    assertions: Optional[dict[str, Any]] = None
    reasoning: str = Field(..., description="Why this test is needed")


class TestAnalysisResponse(BaseModel):
    """Schema for test analysis response."""

    analysis_summary: str = Field(..., description="Overall analysis of test coverage")
    suggested_tests: list[GeneratedTestCase] = Field(..., description="List of suggested test cases")
    coverage_gaps: list[str] = Field(..., description="Areas lacking test coverage")
    recommendations: list[str] = Field(..., description="General testing recommendations")


class TestCodeGenerateRequest(BaseModel):
    """Schema for requesting test code generation."""

    test_case_ids: Optional[list[int]] = Field(None, description="Specific test case IDs to generate (null for all)")


class TestGenerationJobResponse(BaseModel):
    """Schema for test generation job response."""

    id: int
    workspace_id: int
    test_suite_id: int
    status: str = Field(..., description="Job status: pending, running, completed, failed")
    total_tests: int = Field(0, description="Total number of tests to generate")
    completed_tests: int = Field(0, description="Number of tests completed")
    current_test_name: Optional[str] = Field(None, description="Name of test currently being generated")
    current_stage: str = Field(..., description="Current stage: cloning, generating, committing, pushing, completed")
    branch_name: Optional[str] = Field(None, description="Generated branch name")
    base_branch: Optional[str] = Field(None, description="Base branch name")
    generated_files: Optional[list[str]] = Field(None, description="List of generated file paths")
    pr_url: Optional[str] = Field(None, description="Pull request URL")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True
