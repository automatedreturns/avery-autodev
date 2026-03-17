"""Quality Gate Service - Enforce quality standards before PR approval."""

import logging
from sqlalchemy.orm import Session

from app.models.ci_run import CIRun
from app.schemas.ci_run import QualityGateResult

logger = logging.getLogger(__name__)


class QualityGate:
    """Quality gate enforcement for CI runs."""

    @staticmethod
    def check_all_tests_passed(ci_run: CIRun) -> tuple[bool, str]:
        """
        Check if all tests passed.

        Args:
            ci_run: CIRun object

        Returns:
            Tuple of (passed: bool, message: str)
        """
        if ci_run.tests_failed is not None and ci_run.tests_failed > 0:
            return False, f"{ci_run.tests_failed} test(s) failed"

        if ci_run.check_results:
            for check_name, outcome in ci_run.check_results.items():
                if "test" in check_name.lower() and outcome != "success":
                    return False, f"Test check '{check_name}' did not pass"

        return True, "All tests passed"

    @staticmethod
    def check_no_lint_errors(ci_run: CIRun) -> tuple[bool, str]:
        """
        Check if there are no lint errors.

        Args:
            ci_run: CIRun object

        Returns:
            Tuple of (passed: bool, message: str)
        """
        if ci_run.lint_errors_count is not None and ci_run.lint_errors_count > 0:
            return False, f"{ci_run.lint_errors_count} lint error(s) found"

        if ci_run.check_results:
            for check_name, outcome in ci_run.check_results.items():
                if "lint" in check_name.lower() and outcome != "success":
                    return False, f"Lint check '{check_name}' did not pass"

        return True, "No lint errors"

    @staticmethod
    def check_no_type_errors(ci_run: CIRun) -> tuple[bool, str]:
        """
        Check if there are no type errors.

        Args:
            ci_run: CIRun object

        Returns:
            Tuple of (passed: bool, message: str)
        """
        if ci_run.type_errors_count is not None and ci_run.type_errors_count > 0:
            return False, f"{ci_run.type_errors_count} type error(s) found"

        if ci_run.check_results:
            for check_name, outcome in ci_run.check_results.items():
                if "type" in check_name.lower() and outcome != "success":
                    return False, f"Type check '{check_name}' did not pass"

        return True, "No type errors"

    @staticmethod
    def check_build_success(ci_run: CIRun) -> tuple[bool, str]:
        """
        Check if build succeeded.

        Args:
            ci_run: CIRun object

        Returns:
            Tuple of (passed: bool, message: str)
        """
        if ci_run.check_results:
            for check_name, outcome in ci_run.check_results.items():
                if "build" in check_name.lower() and outcome != "success":
                    return False, f"Build check '{check_name}' failed"

        if ci_run.conclusion == "failure":
            return False, "CI run failed"

        return True, "Build succeeded"

    @staticmethod
    def check_coverage_not_decreased(ci_run: CIRun) -> tuple[bool, str]:
        """
        Check if coverage did not decrease.

        Args:
            ci_run: CIRun object

        Returns:
            Tuple of (passed: bool, message: str)
        """
        if ci_run.coverage_delta is not None:
            if ci_run.coverage_delta < 0:
                return False, f"Coverage decreased by {abs(ci_run.coverage_delta):.2f}%"

        return True, "Coverage maintained or improved"

    @staticmethod
    def evaluate(ci_run: CIRun) -> dict:
        """
        Evaluate all quality gates for a CI run.

        Args:
            ci_run: CIRun object

        Returns:
            Dictionary with evaluation results
        """
        checks = {}
        violations = []

        # Run all checks
        check_methods = [
            ("all_tests_passed", QualityGate.check_all_tests_passed),
            ("no_lint_errors", QualityGate.check_no_lint_errors),
            ("no_type_errors", QualityGate.check_no_type_errors),
            ("build_success", QualityGate.check_build_success),
            ("coverage_not_decreased", QualityGate.check_coverage_not_decreased),
        ]

        for check_name, check_method in check_methods:
            passed, message = check_method(ci_run)
            checks[check_name] = passed

            if not passed:
                violations.append(message)

        # Overall pass/fail
        all_passed = all(checks.values())

        # Determine recommendation
        if all_passed:
            recommendation = "approve"
        elif len(violations) <= 1:
            recommendation = "needs_review"
        else:
            recommendation = "request_changes"

        return {
            "passed": all_passed,
            "checks": checks,
            "violations": violations,
            "recommendation": recommendation,
            "coverage_delta": ci_run.coverage_delta
        }


def evaluate_quality_gate(ci_run: CIRun, db: Session) -> QualityGateResult:
    """
    Evaluate quality gate for a CI run.

    Args:
        ci_run: CIRun object
        db: Database session (unused but kept for consistency)

    Returns:
        QualityGateResult schema
    """
    evaluation = QualityGate.evaluate(ci_run)

    return QualityGateResult(
        passed=evaluation["passed"],
        pr_number=ci_run.pr_number,
        checks=evaluation["checks"],
        violations=evaluation["violations"],
        coverage_delta=evaluation["coverage_delta"],
        recommendation=evaluation["recommendation"]
    )
