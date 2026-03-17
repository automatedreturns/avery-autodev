"""
Pydantic schemas for Phase 2 coverage tracking and analysis.

These schemas validate and serialize coverage data for the API layer.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


# Coverage Snapshot Schemas
class FileCoverageDetail(BaseModel):
    """Coverage details for a single file."""

    lines: float = Field(..., description="Line coverage percentage")
    lines_covered: Optional[int] = Field(None, description="Number of lines covered")
    lines_total: Optional[int] = Field(None, description="Total number of lines")
    branches: Optional[float] = Field(None, description="Branch coverage percentage")


class CoverageSnapshotBase(BaseModel):
    """Base coverage snapshot schema."""

    workspace_id: int
    lines_covered: int = Field(..., ge=0)
    lines_total: int = Field(..., gt=0)
    coverage_percent: float = Field(..., ge=0.0, le=100.0)
    branches_covered: Optional[int] = Field(None, ge=0)
    branches_total: Optional[int] = Field(None, ge=0)
    branch_coverage_percent: Optional[float] = Field(None, ge=0.0, le=100.0)
    commit_sha: str = Field(..., min_length=7, max_length=40)
    branch_name: str = Field(..., min_length=1)
    pr_number: Optional[int] = Field(None, gt=0)

    @field_validator('lines_total')
    @classmethod
    def validate_lines_total(cls, v: int, info) -> int:
        """Validate lines_total is greater than 0."""
        if v <= 0:
            raise ValueError('lines_total must be greater than 0')
        return v

    @field_validator('coverage_percent')
    @classmethod
    def validate_coverage_percent(cls, v: float, info) -> float:
        """Validate and round coverage percentage."""
        data = info.data
        if 'lines_covered' in data and 'lines_total' in data and data['lines_total'] > 0:
            calculated = (data['lines_covered'] / data['lines_total']) * 100
            if abs(calculated - v) > 0.1:
                raise ValueError('coverage_percent does not match lines_covered/lines_total')
        return round(v, 2)


class CoverageSnapshotCreate(CoverageSnapshotBase):
    """Schema for creating a new coverage snapshot."""

    file_coverage: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="Per-file coverage breakdown"
    )
    uncovered_lines: dict[str, list[int]] = Field(
        default_factory=dict,
        description="Uncovered line numbers per file"
    )
    uncovered_functions: list[str] = Field(
        default_factory=list,
        description="List of uncovered function names"
    )
    report_format: Optional[str] = Field(None, description="Coverage report format (pytest, jest, etc.)")
    report_path: Optional[str] = Field(None, description="Path to coverage report")
    ci_run_id: Optional[int] = None
    agent_test_generation_id: Optional[int] = None


class CoverageSnapshotResponse(BaseModel):
    """Schema for coverage snapshot in API responses."""

    id: int
    workspace_id: int
    lines_covered: int
    lines_total: int
    coverage_percent: float
    branches_covered: Optional[int]
    branches_total: Optional[int]
    branch_coverage_percent: Optional[float]
    file_coverage: dict[str, dict[str, Any]]
    uncovered_lines: dict[str, list[int]]
    uncovered_functions: list[str]
    commit_sha: str
    branch_name: str
    pr_number: Optional[int]
    report_format: Optional[str]
    report_path: Optional[str]
    ci_run_id: Optional[int]
    agent_test_generation_id: Optional[int]
    created_at: datetime
    coverage_grade: str  # Computed property from model

    class Config:
        from_attributes = True


# Coverage Delta Schemas
class FileCoverageChange(BaseModel):
    """Coverage change for a single file."""

    path: str
    delta: float
    current: float
    previous: float
    status: str  # 'improved' or 'regressed'


class CoverageDeltaResponse(BaseModel):
    """Schema for coverage delta between two snapshots."""

    delta_percent: float = Field(..., description="Overall coverage change")
    delta_lines: int = Field(..., description="Change in covered lines")
    previous_coverage: float = Field(..., description="Previous coverage percentage")
    current_coverage: float = Field(..., description="Current coverage percentage")
    improved: bool = Field(..., description="Whether coverage improved")
    improved_files: list[FileCoverageChange] = Field(
        default_factory=list,
        description="Files with improved coverage"
    )
    regressed_files: list[FileCoverageChange] = Field(
        default_factory=list,
        description="Files with regressed coverage"
    )


class CoverageDeltaRequest(BaseModel):
    """Schema for requesting coverage delta calculation."""

    current_snapshot_id: int
    previous_snapshot_id: Optional[int] = Field(
        None,
        description="Previous snapshot ID (uses latest if not provided)"
    )


# Coverage Trend Schemas
class CoverageTrendResponse(BaseModel):
    """Schema for coverage trend over time."""

    workspace_id: int
    trend_direction: str = Field(..., description="improving, declining, or stable")
    average_coverage: float = Field(..., description="Average coverage over period")
    min_coverage: float = Field(..., description="Minimum coverage in period")
    max_coverage: float = Field(..., description="Maximum coverage in period")
    total_change: float = Field(..., description="Total coverage change")
    days_tracked: int = Field(..., description="Number of days analyzed")
    snapshots_count: int = Field(..., description="Number of snapshots analyzed")
    snapshots: list[CoverageSnapshotResponse] = Field(
        default_factory=list,
        description="Snapshots included in trend"
    )


class CoverageTrendRequest(BaseModel):
    """Schema for requesting coverage trend analysis."""

    workspace_id: int
    days: int = Field(default=30, ge=1, le=365, description="Number of days to analyze")
    branch_name: Optional[str] = Field(None, description="Filter by branch")


# Uncovered Code Schemas
class UncoveredFileDetail(BaseModel):
    """Details about uncovered code in a file."""

    path: str
    uncovered_count: int = Field(..., ge=0)
    uncovered_lines: list[int] = Field(default_factory=list)
    coverage: float = Field(..., ge=0.0, le=100.0)
    priority_score: float = Field(..., description="Priority for test generation")


class UncoveredCodeResponse(BaseModel):
    """Schema for uncovered code identification."""

    snapshot_id: int
    total_uncovered_lines: int = Field(..., ge=0)
    files_with_gaps: int = Field(..., ge=0)
    priority_files: list[UncoveredFileDetail] = Field(
        default_factory=list,
        description="Files prioritized for test generation"
    )
    coverage_percent: float = Field(..., ge=0.0, le=100.0)
    coverage_grade: str = Field(..., description="Coverage grade (A-F)")


class UncoveredCodeRequest(BaseModel):
    """Schema for requesting uncovered code identification."""

    snapshot_id: int
    max_files: int = Field(default=10, ge=1, le=50, description="Maximum files to return")
    max_lines_per_file: int = Field(default=20, ge=1, le=100, description="Maximum lines per file")


# Coverage Analysis Request
class CoverageAnalysisRequest(BaseModel):
    """Schema for requesting full coverage analysis."""

    workspace_id: int
    repo_path: str = Field(..., description="Path to repository")
    framework: str = Field(..., description="Test framework (pytest, jest, mocha)")
    commit_sha: str = Field(..., min_length=7, max_length=40)
    branch_name: str = Field(..., min_length=1)
    ci_run_id: Optional[int] = None
    agent_test_generation_id: Optional[int] = None
    pr_number: Optional[int] = Field(None, gt=0)

    @field_validator('framework')
    @classmethod
    def validate_framework(cls, v: str) -> str:
        """Validate test framework."""
        valid_frameworks = ['pytest', 'jest', 'mocha', 'istanbul', 'coverage.py']
        if v.lower() not in valid_frameworks:
            raise ValueError(f'Framework must be one of: {", ".join(valid_frameworks)}')
        return v.lower()


# Snapshot Comparison Schema
class SnapshotComparisonResponse(BaseModel):
    """Schema for detailed snapshot comparison."""

    snapshot1: dict[str, Any] = Field(..., description="First snapshot summary")
    snapshot2: dict[str, Any] = Field(..., description="Second snapshot summary")
    overall_delta: float = Field(..., description="Overall coverage change")
    lines_delta: int = Field(..., description="Change in covered lines")
    status: str = Field(..., description="improved, regressed, or unchanged")
    file_changes: list[FileCoverageChange] = Field(
        default_factory=list,
        description="Detailed file-level changes"
    )
    total_files_changed: int = Field(..., ge=0)


class SnapshotComparisonRequest(BaseModel):
    """Schema for requesting snapshot comparison."""

    snapshot_id_1: int
    snapshot_id_2: int


# Coverage Report Parsing Response
class CoverageReportParseResponse(BaseModel):
    """Schema for parsed coverage report."""

    coverage_percent: float
    lines_covered: int
    lines_total: int
    branches_covered: Optional[int] = None
    branches_total: Optional[int] = None
    branch_coverage_percent: Optional[float] = None
    file_coverage: dict[str, dict[str, Any]]
    uncovered_lines: dict[str, list[int]]
    uncovered_functions: list[str] = Field(default_factory=list)
