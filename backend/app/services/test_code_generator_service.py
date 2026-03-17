"""Test Code Generator Service for creating actual test files from test case metadata.

This service uses the Claude Agent SDK (ClaudeSDKClient) for test generation,
providing conversation continuity, tool access, and better code generation capabilities.
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.test_case import TestCase
from app.models.test_suite import TestSuite
from app.models.workspace import Workspace
from app.models.agent_test_generation import AgentTestGeneration
from app.services.git_local_service import (
    GitLocalError,
    checkout_branch,
    create_branch,
    ensure_repo_cloned,
    commit_changes,
    push_branch,
)
from app.services.github_service import create_pull_request

logger = logging.getLogger(__name__)


class TestCodeGeneratorError(Exception):
    """Custom exception for test code generation errors."""

    pass


async def generate_test_code_for_case_async(
    test_case: TestCase,
    test_suite: TestSuite,
    workspace: Workspace,
    github_token: str,
    repo_path: str,
    session_id: str | None = None,
) -> tuple[str, str | None]:
    """
    Generate actual test code for a single test case using Claude Agent SDK.

    Uses ClaudeSDKClient for better code generation with tool access and
    conversation continuity support.

    Args:
        test_case: TestCase object with metadata
        test_suite: TestSuite object
        workspace: Workspace object
        github_token: GitHub token
        repo_path: Path to the local repository
        session_id: Optional session ID for conversation continuation

    Returns:
        Tuple of (generated_code, new_session_id)

    Raises:
        TestCodeGeneratorError: If code generation fails
    """
    from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
    from claude_agent_sdk.types import ResultMessage, AssistantMessage, TextBlock

    try:
        # Build prompt for test code generation
        prompt = _build_test_code_prompt(test_case, test_suite)

        # Build system message for test generation context
        system_message = f"""You are an expert software testing engineer specializing in {test_suite.test_framework}.

Your task is to generate production-ready test code for the codebase.

Repository: {workspace.github_repository}
Test Framework: {test_suite.test_framework}
Test Directory: {test_suite.test_directory}

IMPORTANT GUIDELINES:
1. Generate ONLY the test function code (not the entire file)
2. Use proper {test_suite.test_framework} syntax and best practices
3. Include all necessary imports for this specific test
4. Add descriptive comments explaining the test logic
5. Handle edge cases and error scenarios
6. Make it production-ready and maintainable

You have access to the repository to read existing code structure.
Use the Read and Glob tools to understand the codebase if needed.

Return the test code in a code block. No explanations outside the code block.
"""

        # Create ClaudeAgentOptions with resume support
        agent_options = ClaudeAgentOptions(
            system_prompt=system_message,
            model="claude-sonnet-4-5-20250929",
            allowed_tools=[
                "Read",
                "Glob",
                "Grep",
            ],
            max_turns=10,  # Limit turns for test generation
            permission_mode="acceptEdits",
            cwd=repo_path,
            resume=session_id,  # Resume from previous session if available
            env={
                "ANTHROPIC_API_KEY": settings.ANTHROPIC_API_KEY,
            }
        )

        generated_code = ""
        new_session_id = None

        _client = ClaudeSDKClient(options=agent_options)
        async with _client as client:
            await client.query(prompt)

            async for message in client.receive_response():
                msg_type = type(message).__name__

                if msg_type == 'AssistantMessage':
                    content_blocks = getattr(message, 'content', [])
                    for block in content_blocks:
                        if isinstance(block, TextBlock) or type(block).__name__ == 'TextBlock':
                            text = getattr(block, 'text', '')
                            if text:
                                generated_code += text

                elif msg_type == 'ResultMessage':
                    new_session_id = getattr(message, 'session_id', None)
                    result = getattr(message, 'result', None)
                    if result and isinstance(result, str):
                        generated_code = result

        # Extract code from response
        code = _extract_code_from_response(generated_code)

        return code, new_session_id

    except Exception as e:
        logger.error(f"Test code generation failed: {e}")
        raise TestCodeGeneratorError(f"Failed to generate test code: {str(e)}")


def generate_test_code_for_case(
    test_case: TestCase,
    test_suite: TestSuite,
    workspace: Workspace,
    github_token: str,
) -> str:
    """
    Synchronous wrapper for generate_test_code_for_case_async.

    For backward compatibility with existing code.

    Args:
        test_case: TestCase object with metadata
        test_suite: TestSuite object
        workspace: Workspace object
        github_token: GitHub token

    Returns:
        Generated test code as string

    Raises:
        TestCodeGeneratorError: If code generation fails
    """
    # Use a temporary repo path for standalone generation
    repo_path = f"{settings.REPOS_BASE_PATH}/workspace-{workspace.id}/test-generation"

    code, _ = asyncio.run(generate_test_code_for_case_async(
        test_case=test_case,
        test_suite=test_suite,
        workspace=workspace,
        github_token=github_token,
        repo_path=repo_path,
        session_id=None,
    ))

    return code


def generate_and_commit_tests(
    test_suite_id: int,
    workspace: Workspace,
    github_token: str,
    db: Session,
    test_case_ids: list[int] | None = None,
    job_id: int | None = None,
) -> dict[str, Any]:
    """
    Generate test code files, commit to new branch, and prepare for PR.

    Args:
        test_suite_id: Test suite ID
        workspace: Workspace object
        github_token: GitHub token
        db: Database session
        test_case_ids: Optional list of specific test case IDs to generate
        job_id: Optional job ID for progress tracking

    Returns:
        Dictionary with branch name, file paths, and commit info

    Raises:
        TestCodeGeneratorError: If generation or commit fails
    """
    def update_job_progress(stage: str, current_test: str | None = None, completed: int | None = None):
        """Update job progress in database."""
        if job_id:
            from app.models.test_generation_job import TestGenerationJob
            job = db.query(TestGenerationJob).filter(TestGenerationJob.id == job_id).first()
            if job:
                job.current_stage = stage
                if current_test:
                    job.current_test_name = current_test
                if completed is not None:
                    job.completed_tests = completed
                db.commit()
                logger.info(f"Job {job_id}: {stage} - {current_test or ''} ({completed}/{job.total_tests if job else '?'})")

    try:
        # Get test suite and test cases
        test_suite = db.query(TestSuite).filter(TestSuite.id == test_suite_id).first()
        if not test_suite:
            raise TestCodeGeneratorError("Test suite not found")

        # Get test cases
        query = db.query(TestCase).filter(TestCase.test_suite_id == test_suite_id)
        if test_case_ids:
            query = query.filter(TestCase.id.in_(test_case_ids))

        test_cases = query.all()

        if not test_cases:
            raise TestCodeGeneratorError("No test cases found to generate")

        # Update job with total test count
        update_job_progress("cloning", None, 0)

        # Clone repository
        repo_path = f"{settings.REPOS_BASE_PATH}/workspace-{workspace.id}/test-generation"
        ensure_repo_cloned(
            repo_path=repo_path,
            repo_url=workspace.github_repository,
            token=github_token,
        )

        # Checkout dev branch
        checkout_branch(repo_path, workspace.github_dev_branch)

        # Create new branch for tests
        branch_name = f"auto-tests-{test_suite.name.lower().replace(' ', '-')}-{test_suite_id}"
        create_branch(repo_path, branch_name, workspace.github_dev_branch)

        update_job_progress("generating", "Starting generation...", 0)

        # Generate and write test files
        generated_files = []
        test_file_contents = {}
        completed_count = 0

        for test_case in test_cases:
            # Update progress for current test
            update_job_progress("generating", test_case.test_name, completed_count)

            # Generate code
            logger.info(f"Generating code for test: {test_case.test_name}")
            code = generate_test_code_for_case(test_case, test_suite, workspace, github_token)

            completed_count += 1

            # Group by file
            file_path = test_case.file_path
            if file_path not in test_file_contents:
                test_file_contents[file_path] = []

            test_file_contents[file_path].append({
                "test_name": test_case.test_name,
                "code": code,
            })

        # Write test files
        for file_path, tests in test_file_contents.items():
            full_path = os.path.join(repo_path, file_path)

            # Create directory if needed
            os.makedirs(os.path.dirname(full_path), exist_ok=True)

            # Check if file exists and read existing content
            existing_content = ""
            if os.path.exists(full_path):
                with open(full_path, "r", encoding="utf-8") as f:
                    existing_content = f.read()

            # Generate complete file content
            file_content = _merge_test_code(
                existing_content=existing_content,
                new_tests=tests,
                test_framework=test_suite.test_framework,
            )

            # Write file
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(file_content)

            generated_files.append(file_path)
            logger.info(f"Written test file: {file_path}")

        # Update progress - committing
        update_job_progress("committing", f"Committing {len(generated_files)} files", completed_count)

        # Commit changes
        from app.services.git_local_service import commit_changes

        commit_message = f"""Add auto-generated tests for {test_suite.name}

Generated {len(test_cases)} test cases:
{chr(10).join(f'- {tc.test_name}' for tc in test_cases[:10])}
{f'... and {len(test_cases) - 10} more' if len(test_cases) > 10 else ''}

Test Framework: {test_suite.test_framework}
Test Directory: {test_suite.test_directory}

Generated by Avery AI Test Suite
"""

        commit_changes(repo_path, commit_message)

        # Update progress - pushing
        update_job_progress("pushing", f"Pushing branch {branch_name}", completed_count)

        # Push branch
        from app.services.git_local_service import push_branch

        push_branch(repo_path, branch_name, github_token, workspace.github_repository)

        # Update progress - completed
        update_job_progress("completed", "Generation completed successfully", completed_count)

        return {
            "branch_name": branch_name,
            "base_branch": workspace.github_dev_branch,
            "generated_files": generated_files,
            "test_count": len(test_cases),
            "message": f"Successfully generated and committed {len(test_cases)} tests to branch '{branch_name}'",
        }

    except GitLocalError as e:
        logger.error(f"Git error during test generation: {e}")
        raise TestCodeGeneratorError(f"Git operation failed: {str(e)}")
    except Exception as e:
        logger.error(f"Test generation and commit failed: {e}", exc_info=True)
        raise TestCodeGeneratorError(f"Failed to generate and commit tests: {str(e)}")


def _build_test_code_prompt(test_case: TestCase, test_suite: TestSuite) -> str:
    """Build Claude prompt for test code generation."""

    mock_data_str = ""
    if test_case.mock_data:
        mock_data_str = f"\nMock Data Configuration:\n{test_case.mock_data}"

    assertions_str = ""
    if test_case.assertions:
        assertions_str = f"\nExpected Assertions:\n{test_case.assertions}"

    prompt = f"""You are an expert software testing engineer. Generate a complete, production-ready test function.

Test Framework: {test_suite.test_framework}
Test Type: {test_case.test_type}
Test Name: {test_case.test_name}
Description: {test_case.description}{mock_data_str}{assertions_str}

Requirements:
1. Generate ONLY the test function code (not the entire file)
2. Include all necessary imports for this specific test at the top
3. Use proper {test_suite.test_framework} syntax and best practices
4. Include setup/teardown if needed
5. Use the mock data provided (if any)
6. Implement all assertions mentioned
7. Add descriptive comments explaining the test logic
8. Handle edge cases and error scenarios
9. Make it production-ready and maintainable

Return ONLY the test function code in a code block. No explanations outside the code block.
"""

    return prompt


def _extract_code_from_response(response_text: str) -> str:
    """Extract code from Claude's response."""
    # Try to find code block
    if "```" in response_text:
        # Extract content between code fences
        start = response_text.find("```")
        end = response_text.rfind("```")

        if start != -1 and end != -1 and end > start:
            code = response_text[start + 3 : end].strip()

            # Remove language identifier if present
            if code.startswith(("python", "javascript", "typescript", "java")):
                code = "\n".join(code.split("\n")[1:])

            return code

    # If no code block, return entire response
    return response_text.strip()


def _merge_test_code(
    existing_content: str,
    new_tests: list[dict[str, str]],
    test_framework: str,
) -> str:
    """
    Merge new test code with existing file content.

    Args:
        existing_content: Existing file content (if any)
        new_tests: List of dicts with test_name and code
        test_framework: Test framework being used

    Returns:
        Complete file content with merged tests
    """
    if not existing_content:
        # New file - add framework imports and tests
        imports = _get_framework_imports(test_framework)
        test_code = "\n\n".join(test["code"] for test in new_tests)

        return f"""{imports}


{test_code}
"""

    # Existing file - append new tests
    # TODO: Detect duplicate test names and skip or update
    test_code = "\n\n".join(test["code"] for test in new_tests)

    return f"""{existing_content}


# Auto-generated tests
{test_code}
"""


def _get_framework_imports(test_framework: str) -> str:
    """Get standard imports for the test framework."""

    framework = test_framework.lower()

    if framework == "pytest":
        return """import pytest
from unittest.mock import Mock, patch, MagicMock"""

    elif framework == "jest":
        return """import { describe, it, expect, jest, beforeEach, afterEach } from '@jest/globals';"""

    elif framework == "mocha":
        return """import { describe, it, before, after, beforeEach, afterEach } from 'mocha';
import { expect } from 'chai';
import sinon from 'sinon';"""

    elif framework == "junit":
        return """import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.AfterEach;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;"""

    else:
        return "# Add framework-specific imports"


async def process_agent_test_generation_async(
    job: AgentTestGeneration,
    workspace: Workspace,
    github_token: str,
    db: Session,
) -> dict[str, Any]:
    """
    Process an AgentTestGeneration job using Claude Agent SDK.

    This function handles the complete test generation workflow:
    1. Clone/update repository
    2. Create feature branch
    3. Generate tests using ClaudeSDKClient
    4. Write test files
    5. Commit and push changes
    6. Update job status with results

    Args:
        job: AgentTestGeneration job to process
        workspace: Workspace object
        github_token: GitHub token for git operations
        db: Database session

    Returns:
        Dictionary with generation results

    Raises:
        TestCodeGeneratorError: If generation fails
    """
    from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
    from claude_agent_sdk.types import TextBlock
    from app.models.agent_test_generation import TestGenerationStatus

    start_time = datetime.utcnow()
    generated_files = []
    tests_generated_count = 0
    session_id = None

    try:
        # Update status to generating
        job.status = TestGenerationStatus.IN_PROGRESS.value
        db.commit()

        # Clone/update repository
        repo_path = f"{settings.REPOS_BASE_PATH}/workspace-{workspace.id}/test-gen-{job.id}"
        ensure_repo_cloned(
            repo_path=repo_path,
            repo_url=workspace.github_repository,
            token=github_token,
        )

        # Checkout dev branch
        checkout_branch(repo_path, workspace.github_dev_branch)

        # Create new branch for tests
        branch_name = f"auto-tests-gen-{job.id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        create_branch(repo_path, branch_name, workspace.github_dev_branch)

        # Get generation metadata
        metadata = job.agent_run_metadata or {}
        generation_type = metadata.get("generation_type", "unit")
        context = metadata.get("context", "")

        # Detect test framework from workspace or source files
        test_framework = _detect_test_framework(repo_path, job.source_files)
        job.generation_method = generation_type
        db.commit()

        # Build comprehensive system prompt for SDK
        system_prompt = f"""You are an expert software testing engineer.

Your task is to generate comprehensive {generation_type} tests for the specified source files.

Repository: {workspace.github_repository}
Branch: {branch_name}
Test Framework: {test_framework}

Source Files to Test:
{chr(10).join(f'- {f}' for f in job.source_files)}

{f'Additional Context: {context}' if context else ''}

IMPORTANT INSTRUCTIONS:
1. Read each source file to understand the code structure
2. Generate thorough tests covering:
   - Normal/happy path cases
   - Edge cases and boundary conditions
   - Error handling scenarios
3. Use {test_framework} syntax and best practices
4. Include proper imports and setup/teardown
5. Write tests to appropriate test file locations
6. After writing tests, provide a summary of what was generated

Use the available tools (Read, Write, Edit, Glob, Grep) to:
- Read source files
- Write test files to the appropriate locations
- Search for existing test patterns in the codebase

When done, summarize:
- Number of tests generated
- Files created/modified
- Coverage areas addressed
"""

        # Create ClaudeAgentOptions with full tool access for test generation
        agent_options = ClaudeAgentOptions(
            system_prompt=system_prompt,
            model="claude-sonnet-4-5-20250929",
            allowed_tools=[
                "Read",
                "Write",
                "Edit",
                "Glob",
                "Grep",
            ],
            max_turns=50,  # Allow more turns for complex test generation
            permission_mode="acceptEdits",
            cwd=repo_path,
            env={
                "ANTHROPIC_API_KEY": settings.ANTHROPIC_API_KEY,
            }
        )

        # Build the prompt
        prompt = f"""Generate {generation_type} tests for the following source files:

{chr(10).join(f'- {f}' for f in job.source_files)}

Please:
1. Read each source file first
2. Determine the appropriate test file location
3. Generate comprehensive tests
4. Write the test files

{f'Context: {context}' if context else ''}
"""

        logger.info(f"Starting test generation for job {job.id} with {len(job.source_files)} files")

        assistant_content = ""

        # Execute SDK query
        _client = ClaudeSDKClient(options=agent_options)
        async with _client as client:
            await client.query(prompt)

            async for message in client.receive_response():
                msg_type = type(message).__name__

                if msg_type == 'AssistantMessage':
                    content_blocks = getattr(message, 'content', [])
                    for block in content_blocks:
                        if isinstance(block, TextBlock) or type(block).__name__ == 'TextBlock':
                            text = getattr(block, 'text', '')
                            if text:
                                assistant_content += text

                        # Track tool use for file operations
                        block_type = type(block).__name__
                        if block_type == 'ToolUseBlock':
                            tool_name = getattr(block, 'name', '')
                            if tool_name in ['Write', 'Edit']:
                                tool_input = getattr(block, 'input', {})
                                file_path = tool_input.get('file_path', '')
                                if file_path and file_path not in generated_files:
                                    generated_files.append(file_path)
                                    tests_generated_count += 1
                                    logger.info(f"Tracked generated file: {file_path}")

                elif msg_type == 'ResultMessage':
                    session_id = getattr(message, 'session_id', None)
                    # Capture usage info
                    usage = getattr(message, 'usage', None)
                    if usage:
                        job.prompt_tokens_used = usage.get('input_tokens', 0)
                        job.completion_tokens_used = usage.get('output_tokens', 0)

        # Commit changes if files were generated
        if generated_files:
            commit_message = f"""Add auto-generated {generation_type} tests

Generated {tests_generated_count} test(s) for:
{chr(10).join(f'- {f}' for f in job.source_files[:5])}
{f'... and {len(job.source_files) - 5} more' if len(job.source_files) > 5 else ''}

Test files:
{chr(10).join(f'- {f}' for f in generated_files[:10])}

Generated by Avery AI Test Generation (Job #{job.id})
"""
            commit_changes(repo_path, commit_message)
            push_branch(repo_path, branch_name, github_token, workspace.github_repository)

        # Calculate duration
        end_time = datetime.utcnow()
        duration_seconds = (end_time - start_time).total_seconds()

        # Create Pull Request
        pr_title = f"[Avery] Auto-generated tests for Job #{job.id}"
        pr_body = f"""## Test Generation Summary

This PR contains auto-generated tests created by Avery AI.

**Job ID:** #{job.id}
**Trigger Type:** {job.trigger_type}
**Tests Generated:** {tests_generated_count}

### Source Files
{chr(10).join(f'- `{f}`' for f in job.source_files[:10])}
{f'... and {len(job.source_files) - 10} more' if len(job.source_files) > 10 else ''}

### Generated Test Files
{chr(10).join(f'- `{f}`' for f in generated_files[:10])}
{f'... and {len(generated_files) - 10} more' if len(generated_files) > 10 else ''}

---
*Generated by Avery AI Test Generation*
"""

        pr_result = create_pull_request(
            token=github_token,
            repo=workspace.github_repository,
            head=branch_name,
            base=workspace.github_dev_branch,
            title=pr_title,
            body=pr_body,
            draft=True,  # Create as draft PR for review
        )

        pr_number = None
        pr_link = None
        pr_url = f"https://github.com/{workspace.github_repository}/compare/{workspace.github_dev_branch}...{branch_name}"

        if pr_result.get("success"):
            pr_number = pr_result.get("pr_number")
            pr_link = pr_result.get("pr_url")
            logger.info(f"Created PR #{pr_number} for test generation job {job.id}")
        else:
            logger.warning(
                f"Failed to create PR for job {job.id}: {pr_result.get('error')}. "
                f"Branch was pushed successfully, PR can be created manually."
            )

        # Update job with results
        job.status = TestGenerationStatus.COMPLETED.value
        job.generated_test_files = generated_files
        job.tests_generated_count = tests_generated_count
        job.duration_seconds = duration_seconds
        job.completed_at = end_time
        job.validation_passed = tests_generated_count > 0

        # Store branch and PR info in metadata
        existing_metadata = job.agent_run_metadata or {}
        existing_metadata.update({
            "branch_name": branch_name,
            "base_branch": workspace.github_dev_branch,
            "pr_url": pr_url,
            "session_id": session_id,
            "pr_number": pr_number,
            "pr_link": pr_link,
        })
        job.agent_run_metadata = existing_metadata
        db.commit()

        logger.info(
            f"Completed test generation job {job.id}: "
            f"{tests_generated_count} tests, {len(generated_files)} files, "
            f"{duration_seconds:.1f}s"
        )

        return {
            "job_id": job.id,
            "status": "completed",
            "branch_name": branch_name,
            "base_branch": workspace.github_dev_branch,
            "generated_files": generated_files,
            "tests_generated_count": tests_generated_count,
            "duration_seconds": duration_seconds,
            "session_id": session_id,
            "pr_url": pr_url,
            "pr_number": pr_number,
            "pr_link": pr_link,
        }

    except GitLocalError as e:
        logger.error(f"Git error during test generation job {job.id}: {e}")
        job.status = TestGenerationStatus.FAILED.value
        job.error_message = f"Git operation failed: {str(e)}"
        job.completed_at = datetime.utcnow()
        db.commit()
        raise TestCodeGeneratorError(f"Git operation failed: {str(e)}")

    except Exception as e:
        logger.error(f"Test generation job {job.id} failed: {e}", exc_info=True)
        job.status = TestGenerationStatus.FAILED.value
        job.error_message = str(e)[:1000]
        job.completed_at = datetime.utcnow()
        if job.retry_count < job.max_retries:
            job.retry_count += 1
        db.commit()
        raise TestCodeGeneratorError(f"Failed to generate tests: {str(e)}")


def _detect_test_framework(repo_path: str, source_files: list[str]) -> str:
    """
    Detect the test framework from the repository.

    Args:
        repo_path: Path to repository
        source_files: List of source files

    Returns:
        Test framework name (pytest, jest, etc.)
    """
    import json

    # Check for Python pytest
    pytest_indicators = [
        os.path.join(repo_path, "pytest.ini"),
        os.path.join(repo_path, "setup.cfg"),
        os.path.join(repo_path, "pyproject.toml"),
    ]

    for indicator in pytest_indicators:
        if os.path.exists(indicator):
            return "pytest"

    # Check for JavaScript/TypeScript test frameworks
    package_json = os.path.join(repo_path, "package.json")
    if os.path.exists(package_json):
        try:
            with open(package_json, "r") as f:
                data = json.load(f)
                deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                if "jest" in deps:
                    return "jest"
                if "vitest" in deps:
                    return "vitest"
                if "mocha" in deps:
                    return "mocha"
        except Exception:
            pass

    # Default based on file extensions
    if source_files:
        ext = os.path.splitext(source_files[0])[1]
        if ext == ".py":
            return "pytest"
        elif ext in [".js", ".jsx", ".ts", ".tsx"]:
            return "jest"
        elif ext == ".java":
            return "junit"

    return "pytest"  # Default


def process_agent_test_generation(
    job: AgentTestGeneration,
    workspace: Workspace,
    github_token: str,
    db: Session,
) -> dict[str, Any]:
    """
    Synchronous wrapper for process_agent_test_generation_async.

    Args:
        job: AgentTestGeneration job to process
        workspace: Workspace object
        github_token: GitHub token
        db: Database session

    Returns:
        Dictionary with generation results
    """
    return asyncio.run(process_agent_test_generation_async(
        job=job,
        workspace=workspace,
        github_token=github_token,
        db=db,
    ))
