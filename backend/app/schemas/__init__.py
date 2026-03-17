"""Schemas package - imports all Pydantic schemas."""

from app.schemas.workspace_task import (
    AvailableIssuesResponse,
    GitHubIssuePreview,
    WorkspaceTaskCreate,
    WorkspaceTaskListResponse,
    WorkspaceTaskResponse,
)

# Phase 2: Test Policy Schemas
from app.schemas.test_policy import (
    PolicyDecisionResponse,
    PolicyEnforcementRequest,
    PolicyRecommendationResponse,
    PolicyRecommendationsResponse,
    PolicyViolationResponse,
    TestFrameworksConfig,
    TestPolicyConfig,
    TestPolicyResponse,
    TestPolicyUpdate,
)

# Phase 2: Coverage Schemas
from app.schemas.coverage import (
    CoverageAnalysisRequest,
    CoverageDeltaRequest,
    CoverageDeltaResponse,
    CoverageReportParseResponse,
    CoverageSnapshotCreate,
    CoverageSnapshotResponse,
    CoverageTrendRequest,
    CoverageTrendResponse,
    FileCoverageChange,
    FileCoverageDetail,
    SnapshotComparisonRequest,
    SnapshotComparisonResponse,
    UncoveredCodeRequest,
    UncoveredCodeResponse,
    UncoveredFileDetail,
)

# Phase 2: Test Generation Schemas
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

__all__ = [
    # Workspace Task
    "WorkspaceTaskCreate",
    "WorkspaceTaskResponse",
    "WorkspaceTaskListResponse",
    "GitHubIssuePreview",
    "AvailableIssuesResponse",
    # Phase 2: Test Policy
    "TestPolicyConfig",
    "TestPolicyUpdate",
    "TestPolicyResponse",
    "TestFrameworksConfig",
    "PolicyViolationResponse",
    "PolicyDecisionResponse",
    "PolicyEnforcementRequest",
    "PolicyRecommendationResponse",
    "PolicyRecommendationsResponse",
    # Phase 2: Coverage
    "CoverageSnapshotCreate",
    "CoverageSnapshotResponse",
    "FileCoverageDetail",
    "CoverageDeltaRequest",
    "CoverageDeltaResponse",
    "FileCoverageChange",
    "CoverageTrendRequest",
    "CoverageTrendResponse",
    "UncoveredCodeRequest",
    "UncoveredCodeResponse",
    "UncoveredFileDetail",
    "CoverageAnalysisRequest",
    "SnapshotComparisonRequest",
    "SnapshotComparisonResponse",
    "CoverageReportParseResponse",
    # Phase 2: Test Generation
    "AgentTestGenerationCreate",
    "AgentTestGenerationUpdate",
    "AgentTestGenerationResponse",
    "TestGenerationRequest",
    "TestQualityMetrics",
    "TestQualityValidationResponse",
    "TestGenerationStats",
    "TestGenerationStatsRequest",
    "RetryTestGenerationRequest",
    "BatchTestGenerationRequest",
    "BatchTestGenerationResponse",
    "TestGenerationListRequest",
    "TestGenerationListResponse",
]
