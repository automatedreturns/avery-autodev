"""Test Analysis Service for AI-powered test generation using Claude."""

import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

from anthropic import Anthropic
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.test_case import TestCase
from app.models.test_suite import TestSuite
from app.models.workspace import Workspace
from app.services.encryption_service import decrypt_token
from app.services.git_local_service import (
    GitLocalError,
    checkout_branch,
    ensure_repo_cloned,
)

logger = logging.getLogger(__name__)


class TestAnalysisError(Exception):
    """Custom exception for test analysis errors."""

    pass


def analyze_repository_for_tests(
    workspace: Workspace,
    test_suite: TestSuite,
    github_token: str,
    db: Session,
    file_paths: Optional[list[str]] = None,
    focus_areas: Optional[list[str]] = None,
) -> dict[str, Any]:
    """
    Analyze repository code and generate test case suggestions using Claude.

    Args:
        workspace: Workspace object
        test_suite: Test suite object
        github_token: GitHub token for repository access
        db: Database session
        file_paths: Optional specific files to analyze
        focus_areas: Optional areas to focus on (e.g., ['authentication', 'api'])

    Returns:
        Dictionary with analysis results and suggested test cases

    Raises:
        TestAnalysisError: If analysis fails
    """
    try:
        # Clone or update repository
        repo_path = f"{settings.REPOS_BASE_PATH}/workspace-{workspace.id}/test-analysis"
        ensure_repo_cloned(
            repo_path=repo_path,
            repo_url=workspace.github_repository,
            token=github_token,
        )

        # Checkout the dev branch
        checkout_branch(repo_path, workspace.github_dev_branch)

        # Get repository structure
        if file_paths:
            # Analyze specific files
            files_to_analyze = file_paths
        else:
            # Scan local repository for source files
            try:
                all_files = []
                excluded_dirs = {
                    "test", "tests", "__tests__", "node_modules", "dist",
                    "build", ".git", "venv", ".venv", "__pycache__",
                    ".pytest_cache", "coverage", ".coverage"
                }
                excluded_patterns = [
                    ".test.", ".spec.", "_test.py", "_spec.js"
                ]

                source_extensions = (".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go")

                # Walk through the repository directory
                for root, dirs, files in os.walk(repo_path):
                    # Remove excluded directories from dirs to prevent walking into them
                    dirs[:] = [d for d in dirs if d not in excluded_dirs and not d.startswith(".")]

                    for file in files:
                        # Check if file has a source code extension
                        if file.endswith(source_extensions):
                            # Get relative path from repo root
                            full_path = os.path.join(root, file)
                            rel_path = os.path.relpath(full_path, repo_path)

                            # Skip if matches excluded patterns
                            if not any(pattern in rel_path for pattern in excluded_patterns):
                                all_files.append(rel_path)

                # Limit to 20 files for analysis
                files_to_analyze = all_files[:20]

                logger.info(f"Found {len(all_files)} total source files, analyzing {len(files_to_analyze)}")
            except Exception as e:
                logger.error(f"Failed to scan repository directory: {e}")
                files_to_analyze = []

        if not files_to_analyze:
            logger.warning(f"No files to analyze. file_paths provided: {file_paths}, repo_path: {repo_path}")

        # Get existing test cases
        existing_tests = (
            db.query(TestCase)
            .filter(TestCase.test_suite_id == test_suite.id)
            .all()
        )
        existing_test_names = {tc.test_name for tc in existing_tests}

        # Read source code for selected files
        source_codes = {}
        for file_path in files_to_analyze[:10]:  # Limit to 10 files
            try:
                full_path = os.path.join(repo_path, file_path)
                with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                if content and len(content) < 10000:  # Skip very large files
                    source_codes[file_path] = content
                    logger.info(f"Successfully read file: {file_path} ({len(content)} chars)")
                else:
                    logger.info(f"Skipped file (empty or too large): {file_path}")
            except Exception as e:
                logger.warning(f"Could not read file {file_path}: {e}")

        logger.info(f"Read {len(source_codes)} source files successfully")

        if not source_codes:
            raise TestAnalysisError(
                f"No source files found to analyze. "
                f"Tried to read {len(files_to_analyze)} files from repository."
            )

        # Build prompt for Claude
        prompt = _build_analysis_prompt(
            test_framework=test_suite.test_framework,
            source_codes=source_codes,
            existing_test_names=existing_test_names,
            focus_areas=focus_areas,
            test_directory=test_suite.test_directory,
        )

        # Call Claude API
        if not settings.ANTHROPIC_API_KEY:
            raise TestAnalysisError("Anthropic API key not configured")

        client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}],
        )

        # Parse response
        response_text = response.content[0].text
        analysis_result = _parse_analysis_response(response_text)

        return analysis_result

    except GitLocalError as e:
        logger.error(f"Git error during test analysis: {e}")
        raise TestAnalysisError(f"Failed to access repository: {str(e)}")
    except Exception as e:
        logger.error(f"Test analysis failed: {e}")
        raise TestAnalysisError(f"Analysis failed: {str(e)}")


def _build_analysis_prompt(
    test_framework: str,
    source_codes: dict[str, str],
    existing_test_names: set[str],
    focus_areas: Optional[list[str]],
    test_directory: str,
) -> str:
    """
    Build Claude prompt for test analysis.

    Args:
        test_framework: Test framework being used
        source_codes: Dictionary of file paths to source code
        existing_test_names: Set of existing test names
        focus_areas: Optional areas to focus on
        test_directory: Test directory path

    Returns:
        Formatted prompt string
    """
    focus_text = ""
    if focus_areas:
        focus_text = f"\nFocus Areas: {', '.join(focus_areas)}"

    existing_tests_text = ""
    if existing_test_names:
        existing_tests_text = f"\nExisting Tests (do not duplicate):\n{', '.join(list(existing_test_names)[:20])}"

    source_files_text = ""
    for file_path, content in source_codes.items():
        source_files_text += f"\n\n--- File: {file_path} ---\n{content[:3000]}"  # Limit content

    prompt = f"""You are an expert software testing engineer. Analyze the following source code and generate comprehensive test case suggestions.

Test Framework: {test_framework}
Test Directory: {test_directory}{focus_text}{existing_tests_text}

Source Code:{source_files_text}

Please provide:
1. Overall analysis of test coverage needs (2-3 sentences)
2. Suggested test cases with:
   - file_path: Path to test file (e.g., "{test_directory}/test_filename.py")
   - test_name: Descriptive test function name
   - test_type: One of: unit, integration, e2e, performance
   - description: What the test validates
   - mock_data: JSON object with sample mock data structure (if needed)
   - assertions: JSON object describing expected outcomes
   - reasoning: Why this test is important
3. Coverage gaps (areas lacking tests)
4. General recommendations

IMPORTANT: Return ONLY valid JSON in this exact format:
{{
  "analysis_summary": "Brief analysis...",
  "suggested_tests": [
    {{
      "file_path": "{test_directory}/test_example.py",
      "test_name": "test_example_function",
      "test_type": "unit",
      "description": "Test that...",
      "mock_data": {{"key": "value"}},
      "assertions": {{"expected_status": 200}},
      "reasoning": "This test is needed because..."
    }}
  ],
  "coverage_gaps": ["Area 1", "Area 2"],
  "recommendations": ["Recommendation 1", "Recommendation 2"]
}}

Generate 5-10 test case suggestions focusing on:
- Critical functionality
- Edge cases and error handling
- Integration points
- Security vulnerabilities
"""

    return prompt


def _parse_analysis_response(response_text: str) -> dict[str, Any]:
    """
    Parse Claude's JSON response into structured data.

    Args:
        response_text: Raw text response from Claude

    Returns:
        Parsed analysis result dictionary

    Raises:
        TestAnalysisError: If parsing fails
    """
    try:
        # Try to find JSON in response (Claude might add explanation before/after)
        json_start = response_text.find("{")
        json_end = response_text.rfind("}") + 1

        if json_start == -1 or json_end == 0:
            raise ValueError("No JSON found in response")

        json_text = response_text[json_start:json_end]
        result = json.loads(json_text)

        # Validate structure
        required_keys = ["analysis_summary", "suggested_tests", "coverage_gaps", "recommendations"]
        if not all(key in result for key in required_keys):
            raise ValueError(f"Missing required keys. Expected: {required_keys}")

        return result

    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Failed to parse analysis response: {e}")
        logger.error(f"Response text: {response_text}")
        raise TestAnalysisError(f"Failed to parse AI response: {str(e)}")


def create_test_cases_from_analysis(
    test_suite_id: int,
    suggested_tests: list[dict[str, Any]],
    db: Session,
) -> list[TestCase]:
    """
    Create TestCase records from analysis suggestions.

    Args:
        test_suite_id: Test suite ID
        suggested_tests: List of suggested test case dictionaries
        db: Database session

    Returns:
        List of created TestCase objects
    """
    created_cases = []

    for test_data in suggested_tests:
        test_case = TestCase(
            test_suite_id=test_suite_id,
            file_path=test_data.get("file_path", ""),
            test_name=test_data.get("test_name", ""),
            test_type=test_data.get("test_type", "unit"),
            description=test_data.get("description", ""),
            mock_data=test_data.get("mock_data"),
            assertions=test_data.get("assertions"),
            status="active",
        )
        db.add(test_case)
        created_cases.append(test_case)

    db.commit()

    return created_cases
