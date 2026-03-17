"""Test Execution Service for running tests and collecting results."""

import json
import logging
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.test_case import TestCase
from app.models.test_result import TestResult
from app.models.test_run import TestRun
from app.models.test_suite import TestSuite
from app.models.workspace import Workspace
from app.services.git_local_service import GitLocalError, checkout_branch, ensure_repo_cloned
from app.services.coverage_service import CoverageParseError, parse_coverage_report

logger = logging.getLogger(__name__)


class TestExecutionError(Exception):
    """Custom exception for test execution errors."""

    pass


def execute_test_suite(
    workspace: Workspace,
    test_suite: TestSuite,
    test_run: TestRun,
    github_token: str,
    db: Session,
) -> TestRun:
    """
    Execute all tests in a test suite and store results.

    Args:
        workspace: Workspace object
        test_suite: Test suite object
        test_run: Test run object (already created with status='queued')
        github_token: GitHub token for repository access
        db: Database session

    Returns:
        Updated TestRun object with results

    Raises:
        TestExecutionError: If test execution fails
    """
    try:
        # Update test run status
        test_run.status = "running"
        test_run.started_at = datetime.now(timezone.utc)
        db.commit()

        # Clone or update repository
        repo_path = f"{settings.REPOS_BASE_PATH}/workspace-{workspace.id}/test-run-{test_run.id}"
        ensure_repo_cloned(
            repo_path=repo_path,
            repo_url=workspace.github_repository,
            token=github_token,
        )

        # Checkout the specified branch
        checkout_branch(repo_path, test_run.branch_name)

        # Execute tests based on framework
        start_time = time.time()
        execution_result = _execute_tests_by_framework(
            repo_path=repo_path,
            test_framework=test_suite.test_framework,
            test_directory=test_suite.test_directory,
        )
        duration = time.time() - start_time

        # Parse and store results
        test_results = _parse_test_output(
            output=execution_result["output"],
            framework=test_suite.test_framework,
            test_run_id=test_run.id,
            db=db,
        )

        # Parse coverage if available
        coverage_percentage = None
        try:
            coverage_data = parse_coverage_report(repo_path, test_suite.test_framework)
            coverage_percentage = coverage_data.get("coverage_percentage")
        except CoverageParseError as e:
            logger.warning(f"Failed to parse coverage: {e}")

        # Update test run with results
        test_run.status = "completed" if execution_result["success"] else "failed"
        test_run.total_tests = len(test_results)
        test_run.passed_tests = sum(1 for r in test_results if r.status == "passed")
        test_run.failed_tests = sum(1 for r in test_results if r.status == "failed")
        test_run.skipped_tests = sum(1 for r in test_results if r.status == "skipped")
        test_run.duration_seconds = duration
        test_run.coverage_percentage = coverage_percentage
        test_run.completed_at = datetime.now(timezone.utc)

        if not execution_result["success"] and execution_result.get("error"):
            test_run.error_message = execution_result["error"][:1000]

        db.commit()
        db.refresh(test_run)

        return test_run

    except GitLocalError as e:
        logger.error(f"Git error during test execution: {e}")
        test_run.status = "failed"
        test_run.error_message = f"Failed to access repository: {str(e)}"
        test_run.completed_at = datetime.now(timezone.utc)
        db.commit()
        raise TestExecutionError(f"Git error: {str(e)}")
    except Exception as e:
        logger.error(f"Test execution failed: {e}", exc_info=True)
        test_run.status = "failed"
        test_run.error_message = f"Execution failed: {str(e)}"[:1000]
        test_run.completed_at = datetime.now(timezone.utc)
        db.commit()
        raise TestExecutionError(f"Execution failed: {str(e)}")


def _execute_tests_by_framework(
    repo_path: str,
    test_framework: str,
    test_directory: str,
) -> dict[str, Any]:
    """
    Execute tests using the appropriate framework.

    Args:
        repo_path: Path to repository
        test_framework: Test framework name
        test_directory: Directory containing tests

    Returns:
        Dictionary with execution results
    """
    framework_lower = test_framework.lower()

    if framework_lower == "pytest":
        return _run_pytest(repo_path, test_directory)
    elif framework_lower in ["jest", "mocha"]:
        return _run_node_tests(repo_path, test_framework)
    elif framework_lower == "junit":
        return _run_junit(repo_path, test_directory)
    else:
        raise TestExecutionError(f"Unsupported test framework: {test_framework}")


def _run_pytest(repo_path: str, test_directory: str) -> dict[str, Any]:
    """
    Execute pytest tests.

    Args:
        repo_path: Path to repository
        test_directory: Directory containing tests

    Returns:
        Dictionary with test results and output
    """
    try:
        # Check if pytest is installed
        install_result = subprocess.run(
            ["python", "-m", "pip", "install", "-q", "pytest", "pytest-json-report", "pytest-cov", "pytest-env"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=120,
        )

        # Run pytest with JSON report and coverage
        test_path = os.path.join(repo_path, test_directory)
        result = subprocess.run(
            [
                "python",
                "-m",
                "pytest",
                test_directory,
                "--json-report",
                "--json-report-file=.pytest-report.json",
                "--cov=.",
                "--cov-report=xml:coverage.xml",
                "-v",
            ],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout
        )

        # Try to load JSON report
        json_report_path = os.path.join(repo_path, ".pytest-report.json")
        json_output = None
        if os.path.exists(json_report_path):
            with open(json_report_path, "r") as f:
                json_output = json.load(f)

        return {
            "success": result.returncode == 0,
            "output": result.stdout + "\n" + result.stderr,
            "json_output": json_output,
            "error": result.stderr if result.returncode != 0 else None,
            "coverage": None,  # TODO: Add coverage support
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "output": "Test execution timed out after 10 minutes",
            "error": "Timeout",
            "coverage": None,
        }
    except Exception as e:
        logger.error(f"Failed to run pytest: {e}")
        return {
            "success": False,
            "output": str(e),
            "error": str(e),
            "coverage": None,
        }


def _run_node_tests(repo_path: str, test_framework: str) -> dict[str, Any]:
    """
    Execute Node.js tests (jest, mocha).

    Args:
        repo_path: Path to repository
        test_framework: Test framework name

    Returns:
        Dictionary with test results and output
    """
    try:
        # Install dependencies
        install_result = subprocess.run(
            ["npm", "install"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )

        # Run tests with coverage
        if test_framework.lower() == "jest":
            test_cmd = ["npm", "test", "--", "--coverage", "--json", "--outputFile=.jest-report.json"]
        else:  # mocha with nyc
            test_cmd = ["npx", "nyc", "--reporter=json-summary", "npm", "test", "--", "--reporter", "json"]

        result = subprocess.run(
            test_cmd,
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout
        )

        # Try to load JSON report
        json_output = None
        if test_framework.lower() == "jest":
            json_report_path = os.path.join(repo_path, ".jest-report.json")
            if os.path.exists(json_report_path):
                with open(json_report_path, "r") as f:
                    json_output = json.load(f)

        return {
            "success": result.returncode == 0,
            "output": result.stdout + "\n" + result.stderr,
            "json_output": json_output,
            "error": result.stderr if result.returncode != 0 else None,
            "coverage": None,
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "output": "Test execution timed out",
            "error": "Timeout",
            "coverage": None,
        }
    except Exception as e:
        logger.error(f"Failed to run {test_framework}: {e}")
        return {
            "success": False,
            "output": str(e),
            "error": str(e),
            "coverage": None,
        }


def _run_junit(repo_path: str, test_directory: str) -> dict[str, Any]:
    """
    Execute JUnit tests.

    Args:
        repo_path: Path to repository
        test_directory: Directory containing tests

    Returns:
        Dictionary with test results and output
    """
    try:
        # Run maven test
        result = subprocess.run(
            ["mvn", "test", "-Dtest=*"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=600,
        )

        return {
            "success": result.returncode == 0,
            "output": result.stdout + "\n" + result.stderr,
            "error": result.stderr if result.returncode != 0 else None,
            "coverage": None,
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "output": "Test execution timed out",
            "error": "Timeout",
            "coverage": None,
        }
    except Exception as e:
        logger.error(f"Failed to run JUnit: {e}")
        return {
            "success": False,
            "output": str(e),
            "error": str(e),
            "coverage": None,
        }


def _parse_test_output(
    output: str,
    framework: str,
    test_run_id: int,
    db: Session,
) -> list[TestResult]:
    """
    Parse test output and create TestResult records.

    Args:
        output: Raw test output
        framework: Test framework name
        test_run_id: Test run ID
        db: Database session

    Returns:
        List of created TestResult objects
    """
    framework_lower = framework.lower()

    if framework_lower == "pytest":
        return _parse_pytest_output(output, test_run_id, db)
    elif framework_lower == "jest":
        return _parse_jest_output(output, test_run_id, db)
    else:
        # Fallback: create a single result with the output
        result = TestResult(
            test_run_id=test_run_id,
            test_name="Test Execution",
            file_path="unknown",
            status="completed",
            output=output[:10000],  # Limit output size
        )
        db.add(result)
        db.commit()
        return [result]


def _parse_pytest_output(output: str, test_run_id: int, db: Session) -> list[TestResult]:
    """Parse pytest output and create TestResult records."""
    results = []

    # Pattern: test_file.py::test_name PASSED/FAILED
    pattern = r"([\w/]+\.py)::([\w_]+)\s+(PASSED|FAILED|SKIPPED)"
    matches = re.findall(pattern, output)

    for file_path, test_name, status in matches:
        # Extract error message if failed
        error_message = None
        if status == "FAILED":
            error_pattern = rf"{test_name}.*?ERROR.*?(?=test_|$)"
            error_match = re.search(error_pattern, output, re.DOTALL)
            if error_match:
                error_message = error_match.group(0)[:1000]

        result = TestResult(
            test_run_id=test_run_id,
            test_name=test_name,
            file_path=file_path,
            status=status.lower(),
            error_message=error_message,
        )
        db.add(result)
        results.append(result)

    db.commit()
    return results


def _parse_jest_output(output: str, test_run_id: int, db: Session) -> list[TestResult]:
    """Parse jest output and create TestResult records."""
    results = []

    # Pattern: ✓ test name (duration ms)
    # Pattern: ✕ test name
    passed_pattern = r"✓\s+(.*?)\s+\((\d+)\s*ms\)"
    failed_pattern = r"✕\s+(.*)"

    passed_matches = re.findall(passed_pattern, output)
    for test_name, duration in passed_matches:
        result = TestResult(
            test_run_id=test_run_id,
            test_name=test_name.strip(),
            file_path="unknown",
            status="passed",
            duration_seconds=float(duration) / 1000,
        )
        db.add(result)
        results.append(result)

    failed_matches = re.findall(failed_pattern, output)
    for test_name in failed_matches:
        result = TestResult(
            test_run_id=test_run_id,
            test_name=test_name.strip(),
            file_path="unknown",
            status="failed",
        )
        db.add(result)
        results.append(result)

    db.commit()
    return results
