"""Validation pipeline for agent implementations."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .base import ToolContext
from .validation import RunTestsTool, RunBuildTool, RunLinterTool, TypeCheckTool


@dataclass
class ValidationResult:
    """Result from validation pipeline."""
    passed: bool
    steps: list[dict[str, Any]]
    summary: str
    suggestions: list[str]

    def to_message(self) -> str:
        """Convert to human-readable message."""
        if self.passed:
            return f"✅ **VALIDATION PASSED**\n\n{self.summary}\n\nAll validation checks completed successfully."

        message = f"❌ **VALIDATION FAILED**\n\n{self.summary}\n\n"
        message += "**Failed Checks:**\n"

        for step in self.steps:
            if not step.get("passed", False):
                message += f"- {step['name']}: {step.get('error', 'Failed')}\n"

        if self.suggestions:
            message += "\n**Suggestions:**\n"
            for suggestion in self.suggestions:
                message += f"- {suggestion}\n"

        return message


class ValidationPipeline:
    """Pipeline for validating agent implementations."""

    def __init__(self, context: ToolContext):
        self.context = context
        self.repo_path = Path(context.repo_path)

        # Initialize tools
        self.build_tool = RunBuildTool()
        self.test_tool = RunTestsTool()
        self.linter_tool = RunLinterTool()
        self.type_check_tool = TypeCheckTool()

    def validate(self, skip_tests: bool = False) -> ValidationResult:
        """
        Run validation pipeline.

        Args:
            skip_tests: Skip test execution (for quick validation)

        Returns:
            ValidationResult with overall status
        """
        steps = []
        suggestions = []

        # Step 1: Build check
        build_step = self._run_build_check()
        steps.append(build_step)

        if not build_step["passed"]:
            return ValidationResult(
                passed=False,
                steps=steps,
                summary="Build check failed. Fix compilation errors before proceeding.",
                suggestions=build_step.get("suggestions", [])
            )

        # Step 2: Linter check
        linter_step = self._run_linter_check()
        steps.append(linter_step)

        if not linter_step["passed"]:
            suggestions.extend([
                "Run linter with auto-fix: run_linter(fix=true)",
                "Review linter output and fix issues manually"
            ])

        # Step 3: Type check
        type_step = self._run_type_check()
        steps.append(type_step)

        if not type_step["passed"] and type_step.get("applicable", True):
            suggestions.extend([
                "Fix type errors reported by type checker",
                "Add type annotations if missing"
            ])

        # Step 4: Test execution (skip if requested or if earlier checks failed)
        if not skip_tests and linter_step["passed"] and type_step["passed"]:
            test_step = self._run_test_check()
            steps.append(test_step)

            if not test_step["passed"]:
                suggestions.extend([
                    "Review failing tests and fix implementation",
                    "Run specific test with: run_tests(test_path='path/to/test.py')"
                ])
        elif skip_tests:
            steps.append({
                "name": "Tests",
                "passed": True,
                "skipped": True,
                "message": "Skipped (quick validation mode)"
            })

        # Determine overall result
        critical_steps = [build_step, test_step] if not skip_tests else [build_step]
        passed = all(step.get("passed", False) for step in critical_steps)

        # Build summary
        passed_count = sum(1 for step in steps if step.get("passed", False))
        total_count = len([s for s in steps if not s.get("skipped", False)])

        if passed:
            summary = f"All validation checks passed ({passed_count}/{total_count})"
        else:
            summary = f"Validation failed ({passed_count}/{total_count} checks passed)"

        return ValidationResult(
            passed=passed,
            steps=steps,
            summary=summary,
            suggestions=suggestions
        )

    def _run_build_check(self) -> dict[str, Any]:
        """Run build validation."""
        result = self.build_tool.execute({}, self.context)

        if result.data.get("status") == "skipped":
            # No build system detected - this is OK
            return {
                "name": "Build",
                "passed": True,
                "skipped": True,
                "message": "No build system detected (OK)"
            }

        return {
            "name": "Build",
            "passed": result.success,
            "message": result.data.get("output", "")[:500],
            "error": result.error,
            "suggestions": result.suggestions or []
        }

    def _run_linter_check(self) -> dict[str, Any]:
        """Run linter validation."""
        result = self.linter_tool.execute({"fix": False}, self.context)

        if result.data.get("status") == "skipped":
            return {
                "name": "Linter",
                "passed": True,
                "skipped": True,
                "message": "No linter configured (OK)"
            }

        issues_found = result.data.get("status") == "issues_found"

        return {
            "name": "Linter",
            "passed": not issues_found,
            "message": result.data.get("results", []),
            "error": result.error
        }

    def _run_type_check(self) -> dict[str, Any]:
        """Run type checking validation."""
        result = self.type_check_tool.execute({}, self.context)

        if result.data.get("status") == "skipped":
            return {
                "name": "Type Check",
                "passed": True,
                "skipped": True,
                "applicable": False,
                "message": "No type checker configured (OK)"
            }

        return {
            "name": "Type Check",
            "passed": result.success,
            "message": result.data.get("output", "")[:500],
            "error": result.error
        }

    def _run_test_check(self) -> dict[str, Any]:
        """Run test validation."""
        result = self.test_tool.execute({}, self.context)

        if not result.success and result.error and "No test framework detected" in result.error:
            return {
                "name": "Tests",
                "passed": True,
                "skipped": True,
                "message": "No test framework detected (OK)"
            }

        test_status = result.data.get("status")

        return {
            "name": "Tests",
            "passed": test_status == "passed",
            "passed_count": result.data.get("passed", 0),
            "failed_count": result.data.get("failed", 0),
            "total_count": result.data.get("total", 0),
            "message": result.data.get("output", "")[:1000],
            "error": result.error
        }


def should_run_validation(implementation_complete: bool, is_automated: bool) -> bool:
    """
    Determine if validation should be run based on workflow state.

    Args:
        implementation_complete: Whether agent marked implementation complete
        is_automated: Whether this is an automated workflow

    Returns:
        True if validation should run
    """
    # Always validate before marking complete
    return implementation_complete


def format_validation_message(result: ValidationResult, is_automated: bool) -> str:
    """
    Format validation result as a message for the user.

    Args:
        result: Validation result
        is_automated: Whether this is an automated workflow

    Returns:
        Formatted message string
    """
    if result.passed:
        if is_automated:
            return f"""🎉 **VALIDATION COMPLETE**

{result.summary}

The implementation has been validated and is ready for review.
Creating pull request..."""
        else:
            return f"""✅ **VALIDATION PASSED**

{result.summary}

Your changes have been validated successfully. You can now:
- Review the diff with get_git_diff
- Create a pull request
- Continue making additional changes"""

    else:
        base_message = result.to_message()

        if is_automated:
            return f"""{base_message}

**Next Steps:**
I'll work on fixing the validation issues before marking the implementation complete."""
        else:
            return f"""{base_message}

**Next Steps:**
Please review the issues above and either:
1. Let me fix them by describing what needs to change
2. Make changes manually and re-run validation"""
