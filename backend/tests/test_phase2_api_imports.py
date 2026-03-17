"""
Integration tests for Phase 2 API endpoints.

Tests that all Phase 2 API modules import correctly and routers are properly configured.
"""

import pytest


class TestPhase2APIImports:
    """Test Phase 2 API module imports."""

    def test_test_policy_api_imports(self):
        """Test that test_policy API module imports successfully."""
        from app.api.v1 import test_policy

        assert test_policy.router is not None
        assert test_policy.router.prefix == "/{workspace_id}/test-policy"
        assert "test-policy" in test_policy.router.tags

    def test_coverage_api_imports(self):
        """Test that coverage API module imports successfully."""
        from app.api.v1 import coverage

        assert coverage.router is not None
        assert coverage.router.prefix == "/coverage"
        assert "coverage" in coverage.router.tags

    def test_test_generation_api_imports(self):
        """Test that test_generation API module imports successfully."""
        from app.api.v1 import test_generation

        assert test_generation.router is not None
        assert test_generation.router.prefix == "/test-generation"
        assert "test-generation" in test_generation.router.tags


class TestPhase2APIRoutes:
    """Test Phase 2 API route registration."""

    def test_main_app_includes_phase2_routers(self):
        """Test that main FastAPI app includes Phase 2 routers."""
        from app.main import app

        # Get all route paths
        routes = [r.path for r in app.routes if hasattr(r, "path")]

        # Check test policy routes exist
        assert any("test-policy" in r for r in routes), "Test policy routes not found"

        # Check coverage routes exist
        assert any("/coverage/" in r for r in routes), "Coverage routes not found"

        # Check test generation routes exist
        assert any("test-generation" in r for r in routes), "Test generation routes not found"

    def test_phase2_route_count(self):
        """Test that expected number of Phase 2 routes are registered."""
        from app.main import app

        # Count Phase 2 routes
        phase2_routes = [
            r
            for r in app.routes
            if hasattr(r, "path")
            and any(p in r.path for p in ["/test-policy", "/coverage", "/test-generation"])
        ]

        # We expect at least 20 Phase 2 routes (3 test-policy + 10 coverage + 9 test-generation)
        assert len(phase2_routes) >= 20, f"Expected at least 20 Phase 2 routes, found {len(phase2_routes)}"

    def test_test_policy_routes(self):
        """Test test policy routes are registered."""
        from app.main import app

        routes = [r.path for r in app.routes if hasattr(r, "path")]

        # Expected test policy routes
        expected_routes = [
            "/api/v1/workspaces/{workspace_id}/test-policy",
            "/api/v1/workspaces/{workspace_id}/test-policy/enabled",
        ]

        for expected in expected_routes:
            assert expected in routes, f"Route {expected} not found"

    def test_coverage_routes(self):
        """Test coverage routes are registered."""
        from app.main import app

        routes = [r.path for r in app.routes if hasattr(r, "path")]

        # Expected coverage routes
        expected_routes = [
            "/api/v1/coverage/snapshots",
            "/api/v1/coverage/snapshots/{snapshot_id}",
            "/api/v1/coverage/workspaces/{workspace_id}/snapshots",
            "/api/v1/coverage/delta",
            "/api/v1/coverage/compare",
            "/api/v1/coverage/trend",
            "/api/v1/coverage/uncovered",
            "/api/v1/coverage/check-policies",
            "/api/v1/coverage/snapshots/{snapshot_id}/recommendations",
        ]

        for expected in expected_routes:
            assert expected in routes, f"Route {expected} not found"

    def test_test_generation_routes(self):
        """Test test generation routes are registered."""
        from app.main import app

        routes = [r.path for r in app.routes if hasattr(r, "path")]

        # Expected test generation routes
        expected_routes = [
            "/api/v1/test-generation",
            "/api/v1/test-generation/{job_id}",
            "/api/v1/test-generation/workspaces/{workspace_id}/jobs",
            "/api/v1/test-generation/{job_id}/retry",
            "/api/v1/test-generation/batch",
            "/api/v1/test-generation/stats",
            "/api/v1/test-generation/{job_id}/validate",
        ]

        for expected in expected_routes:
            assert expected in routes, f"Route {expected} not found"


class TestPhase2Schemas:
    """Test Phase 2 Pydantic schemas."""

    def test_test_policy_schemas_import(self):
        """Test test policy schemas import successfully."""
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

        # Verify schemas are classes
        assert TestPolicyConfig is not None
        assert TestPolicyUpdate is not None
        assert TestPolicyResponse is not None

    def test_coverage_schemas_import(self):
        """Test coverage schemas import successfully."""
        from app.schemas.coverage import (
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

        # Verify schemas are classes
        assert CoverageSnapshotCreate is not None
        assert CoverageSnapshotResponse is not None
        assert CoverageDeltaResponse is not None

    def test_test_generation_schemas_import(self):
        """Test test generation schemas import successfully."""
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

        # Verify schemas are classes
        assert TestGenerationRequest is not None
        assert AgentTestGenerationResponse is not None
        assert TestQualityValidationResponse is not None


class TestPhase2Services:
    """Test Phase 2 service layer."""

    def test_test_coverage_analyzer_import(self):
        """Test TestCoverageAnalyzer imports successfully."""
        from app.services.test_coverage_analyzer import TestCoverageAnalyzer

        assert TestCoverageAnalyzer is not None

    def test_test_policy_enforcer_import(self):
        """Test TestPolicyEnforcer imports successfully."""
        from app.services.test_policy_enforcer import TestPolicyEnforcer

        assert TestPolicyEnforcer is not None

    def test_services_use_correct_models(self):
        """Test services import correct database models."""
        from app.services.test_coverage_analyzer import TestCoverageAnalyzer
        from app.services.test_policy_enforcer import TestPolicyEnforcer

        # Verify services can be instantiated (they take db as parameter)
        # This ensures all imports work correctly
        assert callable(TestCoverageAnalyzer)
        assert callable(TestPolicyEnforcer)


class TestPhase2Models:
    """Test Phase 2 database models."""

    def test_coverage_snapshot_model_import(self):
        """Test CoverageSnapshot model imports successfully."""
        from app.models.coverage_snapshot import CoverageSnapshot

        assert CoverageSnapshot is not None
        assert CoverageSnapshot.__tablename__ == "coverage_snapshots"

    def test_agent_test_generation_model_import(self):
        """Test AgentTestGeneration model imports successfully."""
        from app.models.agent_test_generation import AgentTestGeneration, TestGenerationStatus

        assert AgentTestGeneration is not None
        assert AgentTestGeneration.__tablename__ == "agent_test_generations"
        assert TestGenerationStatus is not None

    def test_test_generation_status_enum(self):
        """Test TestGenerationStatus enum values."""
        from app.models.agent_test_generation import TestGenerationStatus

        assert TestGenerationStatus.PENDING.value == "pending"
        assert TestGenerationStatus.IN_PROGRESS.value == "generating"
        assert TestGenerationStatus.COMPLETED.value == "completed"
        assert TestGenerationStatus.FAILED.value == "failed"
