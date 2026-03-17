"""
Pydantic schemas for Phase 2 test generation tracking.

These schemas validate and serialize test generation job data for the API layer.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


# Test Generation Base Schemas
class AgentTestGenerationBase(BaseModel):
    """Base schema for agent test generation."""

    workspace_id: int
    trigger_type: str = Field(..., description="Trigger type: feature, bug_fix, manual")
    source_files: list[str] = Field(default_factory=list, description="Source files to generate tests for")
    generation_method: Optional[str] = Field(None, description="Generation method: unit, integration, regression")

    @field_validator('trigger_type')
    @classmethod
    def validate_trigger_type(cls, v: str) -> str:
        """Validate trigger type."""
        valid_types = ['feature', 'bug_fix', 'manual', 'coverage_improvement']
        if v not in valid_types:
            raise ValueError(f'Trigger type must be one of: {", ".join(valid_types)}')
        return v

    @field_validator('generation_method')
    @classmethod
    def validate_generation_method(cls, v: Optional[str]) -> Optional[str]:
        """Validate generation method."""
        if v is not None:
            valid_methods = ['unit', 'integration', 'regression', 'edge_case', 'mixed']
            if v not in valid_methods:
                raise ValueError(f'Generation method must be one of: {", ".join(valid_methods)}')
        return v


class AgentTestGenerationCreate(AgentTestGenerationBase):
    """Schema for creating a new test generation job."""

    agent_job_id: Optional[int] = None
    ci_run_id: Optional[int] = None


class AgentTestGenerationUpdate(BaseModel):
    """Schema for updating test generation job - all fields optional."""

    status: Optional[str] = Field(None, description="Job status")
    generated_test_files: Optional[list[str]] = None
    tests_generated_count: Optional[int] = Field(None, ge=0)
    tests_passed_count: Optional[int] = Field(None, ge=0)
    tests_failed_count: Optional[int] = Field(None, ge=0)
    test_quality_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    coverage_before: Optional[float] = Field(None, ge=0.0, le=100.0)
    coverage_after: Optional[float] = Field(None, ge=0.0, le=100.0)
    coverage_delta: Optional[float] = Field(None, ge=-100.0, le=100.0)
    validation_passed: Optional[bool] = None
    validation_errors: Optional[list[str]] = None
    error_message: Optional[str] = None
    duration_seconds: Optional[float] = Field(None, ge=0.0)

    @field_validator('status')
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        """Validate status."""
        if v is not None:
            valid_statuses = ['pending', 'generating', 'validating', 'completed', 'failed']
            if v not in valid_statuses:
                raise ValueError(f'Status must be one of: {", ".join(valid_statuses)}')
        return v


class AgentTestGenerationResponse(BaseModel):
    """Schema for test generation job in API responses."""

    id: int
    workspace_id: int
    agent_job_id: Optional[int] = None
    ci_run_id: Optional[int] = None
    trigger_type: str
    source_files: list[str]
    generated_test_files: list[str]
    status: str
    generation_method: Optional[str] = None
    tests_generated_count: int = 0
    tests_passed_count: int = 0
    tests_failed_count: int = 0
    test_quality_score: Optional[float] = None
    coverage_before: Optional[float] = None
    coverage_after: Optional[float] = None
    coverage_delta: Optional[float] = None
    validation_passed: bool = False
    validation_errors: list[str] = []
    prompt_tokens_used: int = 0
    completion_tokens_used: int = 0
    duration_seconds: Optional[float] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 2
    agent_run_metadata: Optional[dict[str, Any]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# Test Generation Request Schemas
class TestGenerationRequest(BaseModel):
    """Schema for requesting test generation."""

    workspace_id: int
    files: list[str] = Field(..., min_length=1, description="Files to generate tests for")
    generation_type: str = Field(
        default="unit",
        description="Type of tests to generate: unit, integration, regression"
    )
    trigger_type: str = Field(
        default="manual",
        description="What triggered generation: feature, bug_fix, manual"
    )
    agent_job_id: Optional[int] = None
    ci_run_id: Optional[int] = None
    context: Optional[str] = Field(
        None,
        max_length=10000,
        description="Additional context for test generation"
    )

    @field_validator('files')
    @classmethod
    def validate_files(cls, v: list[str]) -> list[str]:
        """Validate file paths."""
        if not v:
            raise ValueError('At least one file must be provided')
        for file_path in v:
            if not file_path or file_path.strip() == '':
                raise ValueError('File paths cannot be empty')
        return v

    @field_validator('generation_type')
    @classmethod
    def validate_generation_type(cls, v: str) -> str:
        """Validate generation type."""
        valid_types = ['unit', 'integration', 'regression', 'edge_case', 'mixed']
        if v not in valid_types:
            raise ValueError(f'Generation type must be one of: {", ".join(valid_types)}')
        return v


# Test Quality Validation Schemas
class TestQualityMetrics(BaseModel):
    """Test quality metrics for validation."""

    has_assertions: bool = Field(..., description="Tests include assertions")
    has_edge_cases: bool = Field(..., description="Tests cover edge cases")
    has_error_handling: bool = Field(..., description="Tests cover error scenarios")
    has_mocking: bool = Field(..., description="Tests use mocking where appropriate")
    has_setup_teardown: bool = Field(..., description="Tests have proper setup/teardown")
    code_coverage_increase: float = Field(..., description="Coverage increase percentage")
    test_isolation: bool = Field(..., description="Tests are properly isolated")
    naming_conventions: bool = Field(..., description="Tests follow naming conventions")


class TestQualityValidationResponse(BaseModel):
    """Schema for test quality validation results."""

    test_generation_id: int
    quality_score: float = Field(..., ge=0.0, le=100.0, description="Overall quality score")
    metrics: TestQualityMetrics
    passed: bool = Field(..., description="Whether quality threshold was met")
    threshold: float = Field(..., description="Quality threshold")
    suggestions: list[str] = Field(default_factory=list, description="Improvement suggestions")


# Test Generation Statistics
class TestGenerationStats(BaseModel):
    """Statistics for test generation jobs."""

    total_jobs: int = Field(..., ge=0)
    completed_jobs: int = Field(..., ge=0)
    failed_jobs: int = Field(..., ge=0)
    pending_jobs: int = Field(..., ge=0)
    average_quality_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    average_coverage_delta: Optional[float] = None
    total_tests_generated: int = Field(..., ge=0)
    success_rate: float = Field(..., ge=0.0, le=100.0)


class TestGenerationStatsRequest(BaseModel):
    """Schema for requesting test generation statistics."""

    workspace_id: int
    days: int = Field(default=30, ge=1, le=365, description="Number of days to analyze")
    trigger_type: Optional[str] = Field(None, description="Filter by trigger type")


# Retry Test Generation
class RetryTestGenerationRequest(BaseModel):
    """Schema for retrying a failed test generation."""

    test_generation_id: int
    force: bool = Field(
        default=False,
        description="Force retry even if max retries reached"
    )


# Batch Test Generation
class BatchTestGenerationRequest(BaseModel):
    """Schema for generating tests for multiple files at once."""

    workspace_id: int
    files: list[str] = Field(..., min_length=1, max_length=50)
    generation_type: str = Field(default="unit")
    trigger_type: str = Field(default="manual")
    parallel: bool = Field(
        default=True,
        description="Generate tests in parallel"
    )

    @field_validator('files')
    @classmethod
    def validate_batch_files(cls, v: list[str]) -> list[str]:
        """Validate batch file list."""
        if len(v) > 50:
            raise ValueError('Maximum 50 files per batch request')
        return v


class BatchTestGenerationResponse(BaseModel):
    """Schema for batch test generation response."""

    workspace_id: int
    total_files: int
    jobs_created: int
    job_ids: list[int]
    estimated_duration_seconds: Optional[float] = None


# Test Generation Job List
class TestGenerationListRequest(BaseModel):
    """Schema for listing test generation jobs."""

    workspace_id: int
    status: Optional[str] = Field(None, description="Filter by status")
    trigger_type: Optional[str] = Field(None, description="Filter by trigger type")
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)

    @field_validator('status')
    @classmethod
    def validate_status_filter(cls, v: Optional[str]) -> Optional[str]:
        """Validate status filter."""
        if v is not None:
            valid_statuses = ['pending', 'generating', 'validating', 'completed', 'failed']
            if v not in valid_statuses:
                raise ValueError(f'Status must be one of: {", ".join(valid_statuses)}')
        return v


class TestGenerationListResponse(BaseModel):
    """Schema for paginated list of test generation jobs."""

    total: int
    items: list[AgentTestGenerationResponse]
    limit: int
    offset: int
    has_more: bool
