"""Test Discovery Service for automatically importing existing tests."""

import logging
import os
import re
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.test_case import TestCase
from app.models.test_suite import TestSuite
from app.models.workspace import Workspace
from app.services.git_local_service import (
    GitLocalError,
    checkout_branch,
    ensure_repo_cloned,
)

logger = logging.getLogger(__name__)


class TestDiscoveryError(Exception):
    """Custom exception for test discovery errors."""

    pass


def discover_existing_tests(
    test_suite: TestSuite,
    workspace: Workspace,
    github_token: str,
    db: Session,
) -> dict[str, Any]:
    """
    Discover and import existing tests from the repository.

    Args:
        test_suite: Test suite object
        workspace: Workspace object
        github_token: GitHub token for repository access
        db: Database session

    Returns:
        Dictionary with discovered test count and imported tests

    Raises:
        TestDiscoveryError: If discovery fails
    """
    try:
        # Clone repository
        repo_path = f"{settings.REPOS_BASE_PATH}/workspace-{workspace.id}/test-discovery"
        ensure_repo_cloned(
            repo_path=repo_path,
            repo_url=workspace.github_repository,
            token=github_token,
        )

        # Checkout dev branch
        checkout_branch(repo_path, workspace.github_dev_branch)

        # Find test directory
        test_dir = os.path.join(repo_path, test_suite.test_directory)
        if not os.path.exists(test_dir):
            logger.warning(f"Test directory not found: {test_dir}")
            return {
                "discovered_count": 0,
                "imported_count": 0,
                "skipped_count": 0,
                "tests": [],
            }

        # Scan for test files
        test_files = _scan_test_files(test_dir, test_suite.test_framework)
        logger.info(f"Found {len(test_files)} test files in {test_dir}")

        # Parse tests from each file
        all_discovered_tests = []
        for test_file in test_files:
            tests = _parse_test_file(test_file, test_suite.test_framework, repo_path, test_suite.test_directory)
            all_discovered_tests.extend(tests)

        logger.info(f"Discovered {len(all_discovered_tests)} total tests")

        # Get existing test names to avoid duplicates
        existing_tests = (
            db.query(TestCase)
            .filter(TestCase.test_suite_id == test_suite.id)
            .all()
        )
        existing_test_names = {tc.test_name for tc in existing_tests}

        # Import new tests
        imported_tests = []
        skipped_count = 0

        for test_data in all_discovered_tests:
            if test_data["test_name"] in existing_test_names:
                skipped_count += 1
                continue

            test_case = TestCase(
                test_suite_id=test_suite.id,
                file_path=test_data["file_path"],
                test_name=test_data["test_name"],
                test_type=test_data.get("test_type", "unit"),
                description=test_data.get("description"),
                status="active",
            )
            db.add(test_case)
            imported_tests.append(test_case)

        db.commit()

        logger.info(f"Imported {len(imported_tests)} new tests, skipped {skipped_count} existing tests")

        return {
            "discovered_count": len(all_discovered_tests),
            "imported_count": len(imported_tests),
            "skipped_count": skipped_count,
            "tests": [
                {
                    "id": tc.id,
                    "test_name": tc.test_name,
                    "file_path": tc.file_path,
                    "test_type": tc.test_type,
                }
                for tc in imported_tests
            ],
        }

    except GitLocalError as e:
        logger.error(f"Git error during test discovery: {e}")
        raise TestDiscoveryError(f"Failed to access repository: {str(e)}")
    except Exception as e:
        logger.error(f"Test discovery failed: {e}", exc_info=True)
        raise TestDiscoveryError(f"Discovery failed: {str(e)}")


def _scan_test_files(test_dir: str, test_framework: str) -> list[str]:
    """Scan directory for test files based on framework conventions."""
    test_files = []
    framework = test_framework.lower()

    # Define file patterns based on framework
    if framework == "pytest":
        patterns = ["test_*.py", "*_test.py"]
    elif framework in ["jest", "mocha"]:
        patterns = ["*.test.js", "*.test.ts", "*.spec.js", "*.spec.ts", "*.test.jsx", "*.test.tsx"]
    elif framework == "junit":
        patterns = ["*Test.java", "*Tests.java"]
    else:
        # Generic patterns
        patterns = ["test_*", "*_test.*", "*.test.*", "*.spec.*"]

    for root, dirs, files in os.walk(test_dir):
        # Skip node_modules, .venv, etc.
        dirs[:] = [d for d in dirs if d not in ["node_modules", ".venv", "__pycache__", ".pytest_cache"]]

        for file in files:
            file_lower = file.lower()
            if any(
                file_lower.startswith("test_") or
                file_lower.endswith("_test.py") or
                ".test." in file_lower or
                ".spec." in file_lower or
                file_lower.endswith("test.java") or
                file_lower.endswith("tests.java")
                for pattern in patterns
            ):
                test_files.append(os.path.join(root, file))

    return test_files


def _parse_test_file(file_path: str, test_framework: str, repo_path: str, test_directory: str) -> list[dict[str, Any]]:
    """Parse test file to extract test functions/methods."""
    tests = []
    framework = test_framework.lower()

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        # Get relative path from test directory
        rel_path = os.path.relpath(file_path, repo_path)

        if framework == "pytest":
            tests = _parse_pytest(content, rel_path)
        elif framework in ["jest", "mocha"]:
            tests = _parse_javascript_tests(content, rel_path)
        elif framework == "junit":
            tests = _parse_junit(content, rel_path)
        else:
            # Generic parsing
            tests = _parse_generic(content, rel_path)

    except Exception as e:
        logger.warning(f"Failed to parse test file {file_path}: {e}")

    return tests


def _parse_pytest(content: str, file_path: str) -> list[dict[str, Any]]:
    """Parse pytest test functions."""
    tests = []

    # Find test functions: def test_*
    pattern = r"def\s+(test_\w+)\s*\([^)]*\):"
    matches = re.finditer(pattern, content)

    for match in matches:
        test_name = match.group(1)

        # Try to extract docstring
        description = None
        start_pos = match.end()
        docstring_match = re.search(r'"""(.+?)"""', content[start_pos:start_pos+500], re.DOTALL)
        if docstring_match:
            description = docstring_match.group(1).strip()[:200]  # Limit to 200 chars

        tests.append({
            "test_name": test_name,
            "file_path": file_path,
            "test_type": "unit",
            "description": description,
        })

    return tests


def _parse_javascript_tests(content: str, file_path: str) -> list[dict[str, Any]]:
    """Parse Jest/Mocha test functions."""
    tests = []

    # Find test() or it() calls
    patterns = [
        r"(?:test|it)\s*\(\s*['\"]([^'\"]+)['\"]",
        r"(?:test|it)\s*\(\s*`([^`]+)`",
    ]

    for pattern in patterns:
        matches = re.finditer(pattern, content)
        for match in matches:
            test_desc = match.group(1)
            # Convert description to function name format
            test_name = "test_" + re.sub(r'[^\w]+', '_', test_desc.lower()).strip('_')

            tests.append({
                "test_name": test_name,
                "file_path": file_path,
                "test_type": "unit",
                "description": test_desc[:200],
            })

    return tests


def _parse_junit(content: str, file_path: str) -> list[dict[str, Any]]:
    """Parse JUnit test methods."""
    tests = []

    # Find @Test annotated methods
    pattern = r"@Test[^\n]*\s+(?:public\s+)?void\s+(\w+)\s*\(\)"
    matches = re.finditer(pattern, content)

    for match in matches:
        test_name = match.group(1)

        tests.append({
            "test_name": test_name,
            "file_path": file_path,
            "test_type": "unit",
            "description": None,
        })

    return tests


def _parse_generic(content: str, file_path: str) -> list[dict[str, Any]]:
    """Generic test parsing for unknown frameworks."""
    tests = []

    # Look for common test patterns
    patterns = [
        r"def\s+(test_\w+)\s*\(",
        r"function\s+(test\w+)\s*\(",
        r"(?:test|it)\s*\(['\"]([^'\"]+)['\"]",
    ]

    for pattern in patterns:
        matches = re.finditer(pattern, content)
        for match in matches:
            test_name = match.group(1)

            tests.append({
                "test_name": test_name,
                "file_path": file_path,
                "test_type": "unit",
                "description": None,
            })

    return tests
