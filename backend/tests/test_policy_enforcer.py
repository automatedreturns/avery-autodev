"""
Unit tests for Phase 2 TestPolicyEnforcer service.

Tests coverage:
- Policy enforcement for different scenarios
- Minimum coverage validation
- Coverage regression detection
- Test quality validation
- Test requirement checks
- Policy recommendations
"""

import pytest
from datetime import datetime, timedelta

from app.services.test_policy_enforcer import (
    TestPolicyEnforcer,
    PolicyViolation,
    PolicyDecision,
    PolicyViolationSeverity,
)
from app.models.coverage_snapshot import CoverageSnapshot
from app.models.agent_test_generation import AgentTestGeneration
from app.models.workspace import Workspace


class TestPolicyViolationDataclass:
    """Test PolicyViolation dataclass."""

    def test_policy_violation_creation(self):
        """Test creating a PolicyViolation instance."""
        violation = PolicyViolation(
            rule="minimum_coverage",
            severity=PolicyViolationSeverity.ERROR,
            message="Coverage too low",
            current_value=70.0,
            expected_value=80.0,
            fix_suggestion="Add more tests",
        )
        assert violation.rule == "minimum_coverage"
        assert violation.severity == PolicyViolationSeverity.ERROR
        assert violation.message == "Coverage too low"
        assert violation.affected_files == []

    def test_policy_violation_with_affected_files(self):
        """Test PolicyViolation with affected files."""
        violation = PolicyViolation(
            rule="coverage_regression",
            severity=PolicyViolationSeverity.ERROR,
            message="Coverage decreased",
            current_value=75.0,
            expected_value=80.0,
            fix_suggestion="Restore coverage",
            affected_files=["app/foo.py", "app/bar.py"],
        )
        assert len(violation.affected_files) == 2
        assert "app/foo.py" in violation.affected_files


class TestPolicyDecisionDataclass:
    """Test PolicyDecision dataclass."""

    def test_policy_decision_passed(self):
        """Test PolicyDecision when all policies passed."""
        decision = PolicyDecision(
            passed=True,
            violations=[],
            warnings=[],
            info=[],
            summary="All passed",
            coverage_percent=90.0,
        )
        assert decision.passed is True
        assert decision.has_blocking_violations is False
        assert decision.total_issues == 0

    def test_policy_decision_with_violations(self):
        """Test PolicyDecision with violations."""
        violation = PolicyViolation(
            rule="test",
            severity=PolicyViolationSeverity.ERROR,
            message="Test",
            current_value=1,
            expected_value=2,
            fix_suggestion="Fix",
        )
        decision = PolicyDecision(
            passed=False,
            violations=[violation],
            warnings=[],
            info=[],
            summary="Failed",
        )
        assert decision.passed is False
        assert decision.has_blocking_violations is True
        assert decision.total_issues == 1

    def test_policy_decision_total_issues(self):
        """Test total_issues calculation."""
        decision = PolicyDecision(
            passed=True,
            violations=[],
            warnings=[PolicyViolation("w", PolicyViolationSeverity.WARNING, "w", 1, 2, "fix")],
            info=[PolicyViolation("i", PolicyViolationSeverity.INFO, "i", 1, 2, "fix")],
            summary="Some issues",
        )
        assert decision.total_issues == 2


class TestEnforcePolicies:
    """Test enforce_policies method."""

    def test_enforce_policies_workspace_not_found(self, db_session):
        """Test enforcement when workspace doesn't exist."""
        enforcer = TestPolicyEnforcer(db_session)

        decision = enforcer.enforce_policies(
            workspace_id=99999,
            current_snapshot_id=1,
        )

        assert decision.passed is False
        assert len(decision.violations) == 1
        assert decision.violations[0].rule == "workspace_exists"

    def test_enforce_policies_disabled(self, db_session, sample_workspace):
        """Test enforcement when policies are disabled."""
        # Disable policies
        sample_workspace.test_policy_enabled = False
        db_session.commit()

        enforcer = TestPolicyEnforcer(db_session)

        # Create a snapshot (even with low coverage)
        snapshot = CoverageSnapshot(
            workspace_id=sample_workspace.id,
            lines_covered=500,
            lines_total=1000,
            coverage_percent=50.0,
            commit_sha="abc123",
            branch_name="main",
            report_format="pytest",
            report_path="/tmp/repo",
        )
        db_session.add(snapshot)
        db_session.commit()

        decision = enforcer.enforce_policies(
            workspace_id=sample_workspace.id,
            current_snapshot_id=snapshot.id,
        )

        assert decision.passed is True
        assert len(decision.violations) == 0
        assert len(decision.info) == 1
        assert decision.info[0].rule == "policy_disabled"

    def test_enforce_policies_snapshot_not_found(self, db_session, sample_workspace):
        """Test enforcement when snapshot doesn't exist."""
        enforcer = TestPolicyEnforcer(db_session)

        decision = enforcer.enforce_policies(
            workspace_id=sample_workspace.id,
            current_snapshot_id=99999,
        )

        assert decision.passed is False
        assert len(decision.violations) == 1
        assert decision.violations[0].rule == "snapshot_exists"

    def test_enforce_policies_all_pass(self, db_session, sample_workspace):
        """Test enforcement when all policies pass."""
        enforcer = TestPolicyEnforcer(db_session)

        # Create snapshot with good coverage
        snapshot = CoverageSnapshot(
            workspace_id=sample_workspace.id,
            lines_covered=900,
            lines_total=1000,
            coverage_percent=90.0,
            commit_sha="abc123",
            branch_name="main",
            report_format="pytest",
            report_path="/tmp/repo",
        )
        db_session.add(snapshot)
        db_session.commit()

        decision = enforcer.enforce_policies(
            workspace_id=sample_workspace.id,
            current_snapshot_id=snapshot.id,
        )

        assert decision.passed is True
        assert len(decision.violations) == 0
        assert decision.coverage_percent == 90.0
        assert "passed" in decision.summary.lower()

    def test_enforce_policies_coverage_too_low(self, db_session, sample_workspace):
        """Test enforcement when coverage is below minimum."""
        enforcer = TestPolicyEnforcer(db_session)

        # Create snapshot with low coverage (policy requires 80%)
        snapshot = CoverageSnapshot(
            workspace_id=sample_workspace.id,
            lines_covered=700,
            lines_total=1000,
            coverage_percent=70.0,
            commit_sha="abc123",
            branch_name="main",
            report_format="pytest",
            report_path="/tmp/repo",
        )
        db_session.add(snapshot)
        db_session.commit()

        decision = enforcer.enforce_policies(
            workspace_id=sample_workspace.id,
            current_snapshot_id=snapshot.id,
        )

        assert decision.passed is False
        assert len(decision.violations) >= 1

        # Find the minimum coverage violation
        min_cov_violation = next(
            (v for v in decision.violations if v.rule == "minimum_coverage_percent"),
            None
        )
        assert min_cov_violation is not None
        assert min_cov_violation.severity == PolicyViolationSeverity.ERROR
        assert min_cov_violation.current_value == 70.0
        assert min_cov_violation.expected_value == 80.0

    def test_enforce_policies_with_test_generation(self, db_session, sample_workspace):
        """Test enforcement with test generation."""
        enforcer = TestPolicyEnforcer(db_session)

        # Create snapshot
        snapshot = CoverageSnapshot(
            workspace_id=sample_workspace.id,
            lines_covered=850,
            lines_total=1000,
            coverage_percent=85.0,
            commit_sha="abc123",
            branch_name="main",
            report_format="pytest",
            report_path="/tmp/repo",
        )
        db_session.add(snapshot)
        db_session.commit()

        # Create test generation with good quality
        test_gen = AgentTestGeneration(
            workspace_id=sample_workspace.id,
            trigger_type="feature",
            source_files=["app/foo.py"],
            status="completed",
            test_quality_score=85.0,
            tests_generated_count=10,
        )
        db_session.add(test_gen)
        db_session.commit()

        decision = enforcer.enforce_policies(
            workspace_id=sample_workspace.id,
            current_snapshot_id=snapshot.id,
            test_generation_id=test_gen.id,
            change_type="feature",
        )

        assert decision.test_quality_score == 85.0
        assert decision.tests_generated == 10


class TestCheckMinimumCoverage:
    """Test _check_minimum_coverage method."""

    def test_check_minimum_coverage_pass(self, db_session, sample_workspace):
        """Test when coverage meets minimum."""
        enforcer = TestPolicyEnforcer(db_session)

        snapshot = CoverageSnapshot(
            workspace_id=sample_workspace.id,
            lines_covered=850,
            lines_total=1000,
            coverage_percent=85.0,
            commit_sha="abc123",
            branch_name="main",
            report_format="pytest",
            report_path="/tmp/repo",
        )

        violations = enforcer._check_minimum_coverage(snapshot, 80.0)

        assert len(violations) == 0

    def test_check_minimum_coverage_fail(self, db_session, sample_workspace):
        """Test when coverage is below minimum."""
        enforcer = TestPolicyEnforcer(db_session)

        snapshot = CoverageSnapshot(
            workspace_id=sample_workspace.id,
            lines_covered=700,
            lines_total=1000,
            coverage_percent=70.0,
            commit_sha="abc123",
            branch_name="main",
            report_format="pytest",
            report_path="/tmp/repo",
        )

        violations = enforcer._check_minimum_coverage(snapshot, 80.0)

        assert len(violations) == 1
        assert violations[0].rule == "minimum_coverage_percent"
        assert violations[0].severity == PolicyViolationSeverity.ERROR
        assert violations[0].current_value == 70.0
        assert violations[0].expected_value == 80.0


class TestCheckCoverageRegression:
    """Test _check_coverage_regression method."""

    def test_check_coverage_regression_no_previous(self, db_session, sample_workspace):
        """Test when there's no previous snapshot."""
        enforcer = TestPolicyEnforcer(db_session)

        # Create current snapshot
        snapshot = CoverageSnapshot(
            workspace_id=sample_workspace.id,
            lines_covered=800,
            lines_total=1000,
            coverage_percent=80.0,
            commit_sha="abc123",
            branch_name="main",
            report_format="pytest",
            report_path="/tmp/repo",
        )
        db_session.add(snapshot)
        db_session.commit()

        violations = enforcer._check_coverage_regression(
            sample_workspace.id,
            snapshot,
            max_decrease=0.0,
        )

        # No previous snapshot, so no regression
        assert len(violations) == 0

    def test_check_coverage_regression_improved(self, db_session, sample_workspace):
        """Test when coverage improved."""
        enforcer = TestPolicyEnforcer(db_session)

        # Create previous snapshot
        prev_snapshot = CoverageSnapshot(
            workspace_id=sample_workspace.id,
            lines_covered=750,
            lines_total=1000,
            coverage_percent=75.0,
            commit_sha="prev123",
            branch_name="main",
            report_format="pytest",
            report_path="/tmp/repo",
        )
        db_session.add(prev_snapshot)
        db_session.commit()

        # Create current snapshot with better coverage
        curr_snapshot = CoverageSnapshot(
            workspace_id=sample_workspace.id,
            lines_covered=850,
            lines_total=1000,
            coverage_percent=85.0,
            commit_sha="curr123",
            branch_name="main",
            report_format="pytest",
            report_path="/tmp/repo",
        )
        db_session.add(curr_snapshot)
        db_session.commit()

        violations = enforcer._check_coverage_regression(
            sample_workspace.id,
            curr_snapshot,
            max_decrease=0.0,
        )

        # Coverage improved, no violation
        assert len(violations) == 0

    def test_check_coverage_regression_regressed(self, db_session, sample_workspace):
        """Test when coverage regressed."""
        enforcer = TestPolicyEnforcer(db_session)

        # Create previous snapshot with higher coverage
        prev_snapshot = CoverageSnapshot(
            workspace_id=sample_workspace.id,
            lines_covered=900,
            lines_total=1000,
            coverage_percent=90.0,
            file_coverage={"app/foo.py": {"lines": 95.0}},
            commit_sha="prev123",
            branch_name="main",
            report_format="pytest",
            report_path="/tmp/repo",
        )
        db_session.add(prev_snapshot)
        db_session.commit()

        # Create current snapshot with lower coverage
        curr_snapshot = CoverageSnapshot(
            workspace_id=sample_workspace.id,
            lines_covered=800,
            lines_total=1000,
            coverage_percent=80.0,
            file_coverage={"app/foo.py": {"lines": 75.0}},
            commit_sha="curr123",
            branch_name="main",
            report_format="pytest",
            report_path="/tmp/repo",
        )
        db_session.add(curr_snapshot)
        db_session.commit()

        violations = enforcer._check_coverage_regression(
            sample_workspace.id,
            curr_snapshot,
            max_decrease=0.0,
        )

        # Coverage decreased by 10%, should violate
        assert len(violations) == 1
        assert violations[0].rule == "allow_coverage_decrease"
        assert violations[0].severity == PolicyViolationSeverity.ERROR


class TestCheckTestQuality:
    """Test _check_test_quality method."""

    def test_check_test_quality_not_found(self, db_session):
        """Test when test generation doesn't exist."""
        enforcer = TestPolicyEnforcer(db_session)

        violations = enforcer._check_test_quality(99999, 70.0)

        assert len(violations) == 1
        assert violations[0].rule == "test_generation_exists"
        assert violations[0].severity == PolicyViolationSeverity.WARNING

    def test_check_test_quality_failed(self, db_session, sample_workspace):
        """Test when test generation failed."""
        enforcer = TestPolicyEnforcer(db_session)

        test_gen = AgentTestGeneration(
            workspace_id=sample_workspace.id,
            trigger_type="feature",
            source_files=["app/foo.py"],
            status="failed",
            error_message="Failed to generate tests",
        )
        db_session.add(test_gen)
        db_session.commit()

        violations = enforcer._check_test_quality(test_gen.id, 70.0)

        assert len(violations) == 1
        assert violations[0].rule == "test_generation_status"
        assert violations[0].severity == PolicyViolationSeverity.ERROR

    def test_check_test_quality_below_threshold(self, db_session, sample_workspace):
        """Test when quality score is below threshold."""
        enforcer = TestPolicyEnforcer(db_session)

        test_gen = AgentTestGeneration(
            workspace_id=sample_workspace.id,
            trigger_type="feature",
            source_files=["app/foo.py"],
            status="completed",
            test_quality_score=60.0,
        )
        db_session.add(test_gen)
        db_session.commit()

        violations = enforcer._check_test_quality(test_gen.id, 70.0)

        assert len(violations) == 1
        assert violations[0].rule == "test_quality_threshold"
        assert violations[0].severity == PolicyViolationSeverity.WARNING
        assert violations[0].current_value == 60.0

    def test_check_test_quality_pass(self, db_session, sample_workspace):
        """Test when quality score meets threshold."""
        enforcer = TestPolicyEnforcer(db_session)

        test_gen = AgentTestGeneration(
            workspace_id=sample_workspace.id,
            trigger_type="feature",
            source_files=["app/foo.py"],
            status="completed",
            test_quality_score=85.0,
        )
        db_session.add(test_gen)
        db_session.commit()

        violations = enforcer._check_test_quality(test_gen.id, 70.0)

        # Quality is good, no violations
        assert len(violations) == 0


class TestCheckTestRequirements:
    """Test _check_test_requirements method."""

    def test_check_test_requirements_feature_missing(self, db_session, sample_workspace):
        """Test when feature requires tests but none generated."""
        enforcer = TestPolicyEnforcer(db_session)

        snapshot = CoverageSnapshot(
            workspace_id=sample_workspace.id,
            lines_covered=800,
            lines_total=1000,
            coverage_percent=80.0,
            commit_sha="abc123",
            branch_name="main",
            report_format="pytest",
            report_path="/tmp/repo",
        )

        policy_config = {
            "require_tests_for_features": True,
        }

        violations = enforcer._check_test_requirements(
            policy_config,
            "feature",
            None,  # No test generation
            snapshot,
        )

        # Should have an error for missing tests
        error_violations = [v for v in violations if v.severity == PolicyViolationSeverity.ERROR]
        assert len(error_violations) == 1
        assert error_violations[0].rule == "require_tests_for_features"

    def test_check_test_requirements_feature_generated(self, db_session, sample_workspace):
        """Test when feature has tests generated."""
        enforcer = TestPolicyEnforcer(db_session)

        snapshot = CoverageSnapshot(
            workspace_id=sample_workspace.id,
            lines_covered=800,
            lines_total=1000,
            coverage_percent=80.0,
            commit_sha="abc123",
            branch_name="main",
            report_format="pytest",
            report_path="/tmp/repo",
        )

        policy_config = {
            "require_tests_for_features": True,
        }

        violations = enforcer._check_test_requirements(
            policy_config,
            "feature",
            123,  # Test generation ID exists
            snapshot,
        )

        # Should have an info message (tests were generated)
        info_violations = [v for v in violations if v.severity == PolicyViolationSeverity.INFO]
        assert any(v.rule == "require_tests_for_features" for v in info_violations)

    def test_check_test_requirements_bug_fix(self, db_session, sample_workspace):
        """Test when bug fix requires tests."""
        enforcer = TestPolicyEnforcer(db_session)

        snapshot = CoverageSnapshot(
            workspace_id=sample_workspace.id,
            lines_covered=800,
            lines_total=1000,
            coverage_percent=80.0,
            commit_sha="abc123",
            branch_name="main",
            report_format="pytest",
            report_path="/tmp/repo",
        )

        policy_config = {
            "require_tests_for_bug_fixes": True,
        }

        violations = enforcer._check_test_requirements(
            policy_config,
            "bug_fix",
            None,  # No test generation
            snapshot,
        )

        # Should have an error for missing regression tests
        error_violations = [v for v in violations if v.severity == PolicyViolationSeverity.ERROR]
        assert len(error_violations) == 1
        assert error_violations[0].rule == "require_tests_for_bug_fixes"


class TestGetPolicyRecommendations:
    """Test get_policy_recommendations method."""

    def test_get_recommendations_with_gaps(self, db_session, sample_workspace):
        """Test recommendations for coverage gaps."""
        enforcer = TestPolicyEnforcer(db_session)

        snapshot = CoverageSnapshot(
            workspace_id=sample_workspace.id,
            lines_covered=700,
            lines_total=1000,
            coverage_percent=70.0,
            file_coverage={
                "app/foo.py": {"lines": 50.0},
                "app/bar.py": {"lines": 80.0},
            },
            uncovered_lines={
                "app/foo.py": list(range(1, 51)),  # 50 uncovered lines
                "app/bar.py": list(range(1, 21)),  # 20 uncovered lines
            },
            commit_sha="abc123",
            branch_name="main",
            report_format="pytest",
            report_path="/tmp/repo",
        )
        db_session.add(snapshot)
        db_session.commit()

        recommendations = enforcer.get_policy_recommendations(
            sample_workspace.id,
            snapshot.id,
        )

        # Should have recommendations for uncovered files
        assert len(recommendations) > 0

        # First recommendation should be for the file with most gaps
        assert recommendations[0]["type"] == "coverage_gap"
        assert "app/foo.py" in recommendations[0]["file"]

    def test_get_recommendations_declining_trend(self, db_session, sample_workspace):
        """Test recommendations for declining coverage trend."""
        enforcer = TestPolicyEnforcer(db_session)

        # Create declining trend (3 snapshots)
        for i in range(3):
            snapshot = CoverageSnapshot(
                workspace_id=sample_workspace.id,
                lines_covered=900 - (i * 100),
                lines_total=1000,
                coverage_percent=90.0 - (i * 10.0),
                commit_sha=f"commit{i}",
                branch_name="main",
                report_format="pytest",
                report_path="/tmp/repo",
            )
            db_session.add(snapshot)
        db_session.commit()

        # Get latest snapshot
        latest = (
            db_session.query(CoverageSnapshot)
            .filter(CoverageSnapshot.workspace_id == sample_workspace.id)
            .order_by(CoverageSnapshot.created_at.desc())
            .first()
        )

        recommendations = enforcer.get_policy_recommendations(
            sample_workspace.id,
            latest.id,
        )

        # Should have recommendation about declining trend
        trend_recs = [r for r in recommendations if r["type"] == "trend"]
        assert len(trend_recs) > 0
        assert "declining" in trend_recs[0]["title"].lower()

    def test_get_recommendations_improving_trend(self, db_session, sample_workspace):
        """Test recommendations for improving coverage trend."""
        enforcer = TestPolicyEnforcer(db_session)

        # Create improving trend (3 snapshots)
        for i in range(3):
            snapshot = CoverageSnapshot(
                workspace_id=sample_workspace.id,
                lines_covered=700 + (i * 100),
                lines_total=1000,
                coverage_percent=70.0 + (i * 10.0),
                commit_sha=f"commit{i}",
                branch_name="main",
                report_format="pytest",
                report_path="/tmp/repo",
            )
            db_session.add(snapshot)
        db_session.commit()

        # Get latest snapshot
        latest = (
            db_session.query(CoverageSnapshot)
            .filter(CoverageSnapshot.workspace_id == sample_workspace.id)
            .order_by(CoverageSnapshot.created_at.desc())
            .first()
        )

        recommendations = enforcer.get_policy_recommendations(
            sample_workspace.id,
            latest.id,
        )

        # Should have positive recommendation about improving trend
        trend_recs = [r for r in recommendations if r["type"] == "trend"]
        assert len(trend_recs) > 0
        assert "improving" in trend_recs[0]["title"].lower()
