"""
Pydantic schemas for Phase 2 test policy configuration and enforcement.

These schemas validate and serialize test policy data for the API layer.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


# Test Policy Configuration
class TestFrameworksConfig(BaseModel):
    """Test framework configuration per language."""

    backend: str = Field(default="pytest", description="Backend test framework")
    frontend: str = Field(default="jest", description="Frontend test framework")


class TestPolicyConfig(BaseModel):
    """
    Test policy configuration schema.

    Defines workspace-level testing requirements and quality standards.
    """

    require_tests_for_features: bool = Field(
        default=True,
        description="Require tests for new features"
    )
    require_tests_for_bug_fixes: bool = Field(
        default=True,
        description="Require regression tests for bug fixes"
    )
    minimum_coverage_percent: float = Field(
        default=80.0,
        ge=0.0,
        le=100.0,
        description="Minimum required code coverage percentage"
    )
    allow_coverage_decrease: bool = Field(
        default=False,
        description="Allow coverage to decrease"
    )
    max_coverage_decrease_percent: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Maximum allowed coverage decrease"
    )
    require_edge_case_tests: bool = Field(
        default=True,
        description="Require edge case testing"
    )
    require_integration_tests: bool = Field(
        default=False,
        description="Require integration tests"
    )
    test_quality_threshold: float = Field(
        default=70.0,
        ge=0.0,
        le=100.0,
        description="Minimum test quality score (0-100)"
    )
    auto_generate_tests: bool = Field(
        default=True,
        description="Automatically generate tests"
    )
    test_frameworks: TestFrameworksConfig = Field(
        default_factory=TestFrameworksConfig,
        description="Test framework configuration"
    )

    @field_validator('minimum_coverage_percent', 'max_coverage_decrease_percent', 'test_quality_threshold')
    @classmethod
    def validate_percentage(cls, v: float) -> float:
        """Validate percentage values are between 0 and 100."""
        if v < 0 or v > 100:
            raise ValueError('Percentage must be between 0 and 100')
        return round(v, 2)


class TestPolicyUpdate(BaseModel):
    """Schema for updating test policy - all fields optional."""

    require_tests_for_features: Optional[bool] = None
    require_tests_for_bug_fixes: Optional[bool] = None
    minimum_coverage_percent: Optional[float] = Field(None, ge=0.0, le=100.0)
    allow_coverage_decrease: Optional[bool] = None
    max_coverage_decrease_percent: Optional[float] = Field(None, ge=0.0, le=100.0)
    require_edge_case_tests: Optional[bool] = None
    require_integration_tests: Optional[bool] = None
    test_quality_threshold: Optional[float] = Field(None, ge=0.0, le=100.0)
    auto_generate_tests: Optional[bool] = None
    test_frameworks: Optional[TestFrameworksConfig] = None


class TestPolicyResponse(BaseModel):
    """Schema for test policy in API responses."""

    workspace_id: int
    test_policy_enabled: bool
    test_policy_config: TestPolicyConfig

    class Config:
        from_attributes = True


# Policy Violation Schemas
class PolicyViolationResponse(BaseModel):
    """Schema for a single policy violation."""

    rule: str = Field(..., description="Rule that was violated")
    severity: str = Field(..., description="Violation severity: error, warning, info")
    message: str = Field(..., description="Human-readable violation message")
    current_value: Any = Field(..., description="Current value that violates policy")
    expected_value: Any = Field(..., description="Expected value per policy")
    fix_suggestion: str = Field(..., description="Suggested action to fix")
    affected_files: list[str] = Field(default_factory=list, description="Files related to violation")


class PolicyDecisionResponse(BaseModel):
    """Schema for policy enforcement decision."""

    passed: bool = Field(..., description="Whether all policies passed")
    violations: list[PolicyViolationResponse] = Field(
        default_factory=list,
        description="Error-level violations (blocks merge)"
    )
    warnings: list[PolicyViolationResponse] = Field(
        default_factory=list,
        description="Warning-level issues (should fix)"
    )
    info: list[PolicyViolationResponse] = Field(
        default_factory=list,
        description="Informational messages"
    )
    summary: str = Field(..., description="Human-readable summary")
    coverage_percent: Optional[float] = Field(None, description="Current coverage percentage")
    test_quality_score: Optional[float] = Field(None, description="Test quality score (0-100)")
    tests_generated: Optional[int] = Field(None, description="Number of tests generated")

    @property
    def has_blocking_violations(self) -> bool:
        """Check if there are blocking violations."""
        return len(self.violations) > 0

    @property
    def total_issues(self) -> int:
        """Total number of issues."""
        return len(self.violations) + len(self.warnings) + len(self.info)


class PolicyEnforcementRequest(BaseModel):
    """Schema for policy enforcement request."""

    workspace_id: int = Field(..., description="Workspace ID")
    current_snapshot_id: int = Field(..., description="Current coverage snapshot ID")
    test_generation_id: Optional[int] = Field(None, description="Test generation job ID")
    change_type: Optional[str] = Field(
        None,
        description="Type of change: feature, bug_fix, refactor, etc."
    )

    @field_validator('change_type')
    @classmethod
    def validate_change_type(cls, v: Optional[str]) -> Optional[str]:
        """Validate change type."""
        if v is not None:
            valid_types = ['feature', 'bug_fix', 'refactor', 'docs', 'test', 'chore']
            if v not in valid_types:
                raise ValueError(f'Change type must be one of: {", ".join(valid_types)}')
        return v


# Policy Recommendations
class PolicyRecommendationResponse(BaseModel):
    """Schema for a single policy recommendation."""

    priority: int = Field(..., description="Priority (1=highest)")
    type: str = Field(..., description="Recommendation type: coverage_gap, trend, etc.")
    title: str = Field(..., description="Recommendation title")
    description: str = Field(..., description="Detailed description")
    action: str = Field(..., description="Recommended action")
    file: Optional[str] = Field(None, description="Related file")
    lines: list[int] = Field(default_factory=list, description="Related line numbers")


class PolicyRecommendationsResponse(BaseModel):
    """Schema for list of policy recommendations."""

    workspace_id: int
    snapshot_id: int
    recommendations: list[PolicyRecommendationResponse]
    total_recommendations: int

    @property
    def high_priority_count(self) -> int:
        """Count of high priority (1-3) recommendations."""
        return sum(1 for r in self.recommendations if r.priority <= 3)
