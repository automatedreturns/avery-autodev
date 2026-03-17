"""
Phase 2: Test Policy Enforcer Service

Enforces test quality policies defined at the workspace level. Validates that code
changes meet test requirements, coverage thresholds, and quality standards before
allowing merges.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.workspace import Workspace
from app.models.coverage_snapshot import CoverageSnapshot
from app.models.agent_test_generation import AgentTestGeneration
from app.services.test_coverage_analyzer import TestCoverageAnalyzer

logger = logging.getLogger(__name__)


class PolicyViolationSeverity(str, Enum):
    """Severity levels for policy violations."""
    ERROR = "error"  # Blocks merge
    WARNING = "warning"  # Doesn't block, but should be addressed
    INFO = "info"  # Informational only


@dataclass
class PolicyViolation:
    """Represents a single policy violation."""

    rule: str  # Rule that was violated (e.g., "minimum_coverage_percent")
    severity: PolicyViolationSeverity
    message: str  # Human-readable violation message
    current_value: Any  # Current value that violates policy
    expected_value: Any  # Expected value per policy
    fix_suggestion: str  # Suggested action to fix
    affected_files: list[str] = None  # Files related to violation

    def __post_init__(self):
        """Initialize optional fields."""
        if self.affected_files is None:
            self.affected_files = []


@dataclass
class PolicyDecision:
    """Result of policy enforcement check."""

    passed: bool  # Whether all policies passed
    violations: list[PolicyViolation]
    warnings: list[PolicyViolation]
    info: list[PolicyViolation]
    summary: str  # Human-readable summary
    coverage_percent: Optional[float] = None
    test_quality_score: Optional[float] = None
    tests_generated: Optional[int] = None

    @property
    def has_blocking_violations(self) -> bool:
        """Check if there are any blocking (ERROR) violations."""
        return len(self.violations) > 0

    @property
    def total_issues(self) -> int:
        """Total number of issues found."""
        return len(self.violations) + len(self.warnings) + len(self.info)


class TestPolicyEnforcer:
    """
    Phase 2: Enforces test quality policies for workspaces.

    This service:
    1. Validates test coverage meets minimum requirements
    2. Checks for coverage regressions
    3. Validates test quality scores
    4. Enforces test requirements for features and bug fixes
    5. Provides actionable recommendations
    """

    def __init__(self, db: Session):
        """
        Initialize the policy enforcer.

        Args:
            db: Database session
        """
        self.db = db
        self.coverage_analyzer = TestCoverageAnalyzer(db)

    def enforce_policies(
        self,
        workspace_id: int,
        current_snapshot_id: int,
        test_generation_id: Optional[int] = None,
        change_type: Optional[str] = None,  # 'feature', 'bug_fix', 'refactor', etc.
    ) -> PolicyDecision:
        """
        Enforce all test policies for a workspace.

        Args:
            workspace_id: Workspace ID
            current_snapshot_id: Current coverage snapshot ID
            test_generation_id: Optional test generation job ID
            change_type: Type of change being made

        Returns:
            PolicyDecision with violations and recommendations
        """
        workspace = self.db.query(Workspace).filter(
            Workspace.id == workspace_id
        ).first()

        if not workspace:
            logger.error(f"Workspace {workspace_id} not found")
            return PolicyDecision(
                passed=False,
                violations=[PolicyViolation(
                    rule="workspace_exists",
                    severity=PolicyViolationSeverity.ERROR,
                    message=f"Workspace {workspace_id} not found",
                    current_value=None,
                    expected_value=workspace_id,
                    fix_suggestion="Verify workspace ID",
                )],
                warnings=[],
                info=[],
                summary="Workspace not found",
            )

        if not workspace.test_policy_enabled:
            logger.info(f"Test policies disabled for workspace {workspace_id}")
            return PolicyDecision(
                passed=True,
                violations=[],
                warnings=[],
                info=[PolicyViolation(
                    rule="policy_disabled",
                    severity=PolicyViolationSeverity.INFO,
                    message="Test policies are disabled for this workspace",
                    current_value=False,
                    expected_value=True,
                    fix_suggestion="Enable test policies in workspace settings",
                )],
                summary="Test policies disabled - all checks passed",
            )

        policy_config = workspace.test_policy_config or {}
        violations = []
        warnings = []
        info = []

        # Get current snapshot
        current_snapshot = self.db.query(CoverageSnapshot).filter(
            CoverageSnapshot.id == current_snapshot_id
        ).first()

        if not current_snapshot:
            violations.append(PolicyViolation(
                rule="snapshot_exists",
                severity=PolicyViolationSeverity.ERROR,
                message=f"Coverage snapshot {current_snapshot_id} not found",
                current_value=None,
                expected_value=current_snapshot_id,
                fix_suggestion="Generate coverage report before running policy checks",
            ))
            return PolicyDecision(
                passed=False,
                violations=violations,
                warnings=[],
                info=[],
                summary="Coverage snapshot not found",
            )

        # 1. Check minimum coverage requirement
        min_coverage = policy_config.get("minimum_coverage_percent", 80.0)
        coverage_violations = self._check_minimum_coverage(
            current_snapshot, min_coverage
        )
        violations.extend([v for v in coverage_violations if v.severity == PolicyViolationSeverity.ERROR])
        warnings.extend([v for v in coverage_violations if v.severity == PolicyViolationSeverity.WARNING])

        # 2. Check for coverage regression
        if not policy_config.get("allow_coverage_decrease", False):
            regression_violations = self._check_coverage_regression(
                workspace_id,
                current_snapshot,
                policy_config.get("max_coverage_decrease_percent", 0.0)
            )
            violations.extend([v for v in regression_violations if v.severity == PolicyViolationSeverity.ERROR])
            warnings.extend([v for v in regression_violations if v.severity == PolicyViolationSeverity.WARNING])

        # 3. Check test quality score (if test generation occurred)
        if test_generation_id:
            quality_violations = self._check_test_quality(
                test_generation_id,
                policy_config.get("test_quality_threshold", 70.0)
            )
            violations.extend([v for v in quality_violations if v.severity == PolicyViolationSeverity.ERROR])
            warnings.extend([v for v in quality_violations if v.severity == PolicyViolationSeverity.WARNING])

        # 4. Check if tests are required for this change type
        if change_type:
            requirement_violations = self._check_test_requirements(
                policy_config,
                change_type,
                test_generation_id,
                current_snapshot
            )
            violations.extend([v for v in requirement_violations if v.severity == PolicyViolationSeverity.ERROR])
            warnings.extend([v for v in requirement_violations if v.severity == PolicyViolationSeverity.WARNING])
            info.extend([v for v in requirement_violations if v.severity == PolicyViolationSeverity.INFO])

        # Build summary
        passed = len(violations) == 0
        summary = self._build_summary(passed, violations, warnings, info, current_snapshot)

        # Get test generation data if available
        test_quality_score = None
        tests_generated = None
        if test_generation_id:
            test_gen = self.db.query(AgentTestGeneration).filter(
                AgentTestGeneration.id == test_generation_id
            ).first()
            if test_gen:
                test_quality_score = test_gen.test_quality_score
                tests_generated = test_gen.tests_generated_count

        return PolicyDecision(
            passed=passed,
            violations=violations,
            warnings=warnings,
            info=info,
            summary=summary,
            coverage_percent=current_snapshot.coverage_percent,
            test_quality_score=test_quality_score,
            tests_generated=tests_generated,
        )

    def _check_minimum_coverage(
        self,
        snapshot: CoverageSnapshot,
        min_coverage: float,
    ) -> list[PolicyViolation]:
        """
        Check if coverage meets minimum requirement.

        Args:
            snapshot: Coverage snapshot to check
            min_coverage: Minimum required coverage percentage

        Returns:
            List of violations
        """
        violations = []

        if snapshot.coverage_percent < min_coverage:
            gap = min_coverage - snapshot.coverage_percent
            violations.append(PolicyViolation(
                rule="minimum_coverage_percent",
                severity=PolicyViolationSeverity.ERROR,
                message=f"Coverage {snapshot.coverage_percent:.1f}% is below minimum {min_coverage:.1f}%",
                current_value=round(snapshot.coverage_percent, 2),
                expected_value=min_coverage,
                fix_suggestion=f"Add tests to increase coverage by {gap:.1f}%. Focus on files with lowest coverage.",
            ))

        return violations

    def _check_coverage_regression(
        self,
        workspace_id: int,
        current_snapshot: CoverageSnapshot,
        max_decrease: float,
    ) -> list[PolicyViolation]:
        """
        Check if coverage has regressed compared to previous snapshot.

        Args:
            workspace_id: Workspace ID
            current_snapshot: Current coverage snapshot
            max_decrease: Maximum allowed decrease in coverage percentage

        Returns:
            List of violations
        """
        violations = []

        # Get delta from previous snapshot
        delta = self.coverage_analyzer.calculate_coverage_delta(current_snapshot.id)

        if not delta:
            # No previous snapshot to compare
            return violations

        if not delta.improved:
            decrease = abs(delta.delta_percent)
            if decrease > max_decrease:
                violations.append(PolicyViolation(
                    rule="allow_coverage_decrease",
                    severity=PolicyViolationSeverity.ERROR,
                    message=f"Coverage decreased by {decrease:.1f}% (max allowed: {max_decrease:.1f}%)",
                    current_value=round(delta.current_coverage, 2),
                    expected_value=round(delta.previous_coverage, 2),
                    fix_suggestion=f"Add tests to restore coverage. Regressed files: {', '.join([f['path'] for f in delta.regressed_files[:3]])}",
                    affected_files=[f["path"] for f in delta.regressed_files[:10]],
                ))

        return violations

    def _check_test_quality(
        self,
        test_generation_id: int,
        quality_threshold: float,
    ) -> list[PolicyViolation]:
        """
        Check if generated tests meet quality threshold.

        Args:
            test_generation_id: Test generation job ID
            quality_threshold: Minimum quality score (0-100)

        Returns:
            List of violations
        """
        violations = []

        test_gen = self.db.query(AgentTestGeneration).filter(
            AgentTestGeneration.id == test_generation_id
        ).first()

        if not test_gen:
            violations.append(PolicyViolation(
                rule="test_generation_exists",
                severity=PolicyViolationSeverity.WARNING,
                message=f"Test generation {test_generation_id} not found",
                current_value=None,
                expected_value=test_generation_id,
                fix_suggestion="Verify test generation completed successfully",
            ))
            return violations

        if test_gen.status == "failed":
            violations.append(PolicyViolation(
                rule="test_generation_status",
                severity=PolicyViolationSeverity.ERROR,
                message=f"Test generation failed: {test_gen.error_message or 'Unknown error'}",
                current_value="failed",
                expected_value="completed",
                fix_suggestion="Review error logs and retry test generation",
            ))
            return violations

        if test_gen.test_quality_score is not None:
            if test_gen.test_quality_score < quality_threshold:
                gap = quality_threshold - test_gen.test_quality_score
                violations.append(PolicyViolation(
                    rule="test_quality_threshold",
                    severity=PolicyViolationSeverity.WARNING,
                    message=f"Test quality score {test_gen.test_quality_score:.0f}/100 is below threshold {quality_threshold:.0f}/100",
                    current_value=round(test_gen.test_quality_score, 1),
                    expected_value=quality_threshold,
                    fix_suggestion=f"Improve test quality by {gap:.0f} points. Consider adding assertions, edge cases, and integration tests.",
                ))

        return violations

    def _check_test_requirements(
        self,
        policy_config: dict,
        change_type: str,
        test_generation_id: Optional[int],
        current_snapshot: CoverageSnapshot,
    ) -> list[PolicyViolation]:
        """
        Check if tests are required for this change type.

        Args:
            policy_config: Workspace test policy configuration
            change_type: Type of change ('feature', 'bug_fix', etc.)
            test_generation_id: Test generation job ID (if tests were generated)
            current_snapshot: Current coverage snapshot

        Returns:
            List of violations
        """
        violations = []

        # Check if tests are required for features
        if change_type == "feature" and policy_config.get("require_tests_for_features", True):
            if not test_generation_id:
                violations.append(PolicyViolation(
                    rule="require_tests_for_features",
                    severity=PolicyViolationSeverity.ERROR,
                    message="Tests are required for new features",
                    current_value=False,
                    expected_value=True,
                    fix_suggestion="Generate tests for the new feature code or disable this requirement",
                ))
            else:
                violations.append(PolicyViolation(
                    rule="require_tests_for_features",
                    severity=PolicyViolationSeverity.INFO,
                    message="Tests were generated for this feature",
                    current_value=True,
                    expected_value=True,
                    fix_suggestion="Review generated tests for completeness",
                ))

        # Check if tests are required for bug fixes
        if change_type == "bug_fix" and policy_config.get("require_tests_for_bug_fixes", True):
            if not test_generation_id:
                violations.append(PolicyViolation(
                    rule="require_tests_for_bug_fixes",
                    severity=PolicyViolationSeverity.ERROR,
                    message="Tests are required for bug fixes (regression tests)",
                    current_value=False,
                    expected_value=True,
                    fix_suggestion="Add regression tests to prevent this bug from recurring",
                ))
            else:
                violations.append(PolicyViolation(
                    rule="require_tests_for_bug_fixes",
                    severity=PolicyViolationSeverity.INFO,
                    message="Regression tests were generated for this bug fix",
                    current_value=True,
                    expected_value=True,
                    fix_suggestion="Verify tests reproduce the original bug",
                ))

        # Check if edge case tests are required
        if policy_config.get("require_edge_case_tests", True):
            # This is a heuristic - we can't automatically verify edge cases
            violations.append(PolicyViolation(
                rule="require_edge_case_tests",
                severity=PolicyViolationSeverity.INFO,
                message="Policy requires edge case tests",
                current_value="unknown",
                expected_value=True,
                fix_suggestion="Manually verify that edge cases are covered (null values, boundary conditions, error cases)",
            ))

        # Check if integration tests are required
        if policy_config.get("require_integration_tests", False):
            violations.append(PolicyViolation(
                rule="require_integration_tests",
                severity=PolicyViolationSeverity.INFO,
                message="Policy requires integration tests",
                current_value="unknown",
                expected_value=True,
                fix_suggestion="Ensure integration tests cover interactions between components",
            ))

        return violations

    def _build_summary(
        self,
        passed: bool,
        violations: list[PolicyViolation],
        warnings: list[PolicyViolation],
        info: list[PolicyViolation],
        snapshot: CoverageSnapshot,
    ) -> str:
        """
        Build human-readable summary of policy check.

        Args:
            passed: Whether all policies passed
            violations: Error-level violations
            warnings: Warning-level violations
            info: Info-level violations
            snapshot: Coverage snapshot

        Returns:
            Summary string
        """
        if passed:
            summary = f"✅ All test policies passed. Coverage: {snapshot.coverage_percent:.1f}% (Grade {snapshot.get_coverage_grade()})"
            if warnings:
                summary += f". {len(warnings)} warning(s)."
        else:
            summary = f"❌ {len(violations)} policy violation(s) found. Coverage: {snapshot.coverage_percent:.1f}%"
            if warnings:
                summary += f". {len(warnings)} warning(s)."

        return summary

    def get_policy_recommendations(
        self,
        workspace_id: int,
        current_snapshot_id: int,
    ) -> list[dict[str, Any]]:
        """
        Get actionable recommendations for improving test coverage and quality.

        Args:
            workspace_id: Workspace ID
            current_snapshot_id: Current coverage snapshot ID

        Returns:
            List of recommendations with priority and actions
        """
        recommendations = []

        # Get uncovered code
        uncovered = self.coverage_analyzer.identify_uncovered_code(
            current_snapshot_id,
            max_files=10,
        )

        if uncovered.get("priority_files"):
            for i, file_info in enumerate(uncovered["priority_files"][:5], 1):
                recommendations.append({
                    "priority": i,
                    "type": "coverage_gap",
                    "title": f"Add tests for {file_info['path']}",
                    "description": f"File has {file_info['uncovered_count']} uncovered lines ({file_info['coverage']:.1f}% coverage)",
                    "action": f"Focus on lines: {', '.join(map(str, file_info['uncovered_lines'][:10]))}",
                    "file": file_info["path"],
                    "lines": file_info["uncovered_lines"],
                })

        # Get coverage trend
        trend = self.coverage_analyzer.get_coverage_trend(workspace_id, days=30)
        if trend:
            if trend.trend_direction == "declining":
                recommendations.append({
                    "priority": 1,
                    "type": "trend",
                    "title": "Coverage is declining",
                    "description": f"Coverage decreased by {abs(trend.total_change):.1f}% over {trend.days_tracked} days",
                    "action": "Review recent changes and add tests for new code",
                })
            elif trend.trend_direction == "improving":
                recommendations.append({
                    "priority": 10,
                    "type": "trend",
                    "title": "Coverage is improving",
                    "description": f"Coverage increased by {trend.total_change:.1f}% over {trend.days_tracked} days",
                    "action": "Keep up the good work!",
                })

        # Sort by priority
        recommendations.sort(key=lambda x: x["priority"])

        return recommendations
