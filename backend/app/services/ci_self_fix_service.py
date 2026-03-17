"""CI Self-Fix Service - Agent analyzes CI failures and generates fixes."""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from anthropic import Anthropic
from sqlalchemy.orm import Session

from app.core.config import settings
from app.engine.plugins import ExecutionContext, ExecutionUsage, get_plugin
from app.models.ci_run import CIRun
from app.models.workspace import Workspace
from app.services.encryption_service import decrypt_token
from app.services.github_actions_service import GitHubActionsService
from app.services.git_providers import get_git_provider_for_workspace

logger = logging.getLogger(__name__)


class CISelfFixError(Exception):
    """Custom exception for CI self-fix operations."""
    pass


async def handle_ci_failure(ci_run: CIRun, workspace_id: int, db: Session) -> dict:
    """
    Agent analyzes CI failure and attempts to fix it.

    This is the main entry point for the CI self-fix workflow:
    1. Mark as attempting self-fix
    2. Fetch CI logs and parse errors
    3. Build context prompt for Claude
    4. Generate fixes using Claude
    5. Apply fixes and push to PR branch
    6. Wait for new CI run

    Args:
        ci_run: CIRun object that failed
        workspace_id: Workspace ID
        db: Database session

    Returns:
        Dictionary with fix status and details

    Raises:
        CISelfFixError: If self-fix process fails
    """
    # Mark as attempting self-fix
    ci_run.self_fix_attempted = True
    ci_run.retry_count += 1
    db.commit()

    logger.info(
        f"Starting CI self-fix for run {ci_run.id}, "
        f"PR #{ci_run.pr_number}, retry {ci_run.retry_count}/{ci_run.max_retries}"
    )

    plugin = get_plugin()

    # Plugin: before_execute
    ctx = ExecutionContext(
        action="ci_fix",
        user_id=str(ci_run.pr_number),  # Best available identifier
        workspace_id=str(workspace_id),
        metadata={"ci_run_id": str(ci_run.id), "pr_number": ci_run.pr_number},
    )
    ctx = plugin.before_execute(ctx)

    try:
        # Get workspace and GitHub token
        workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
        if not workspace or not workspace.owner.github_token_encrypted:
            raise CISelfFixError("Workspace or GitHub token not found")

        github_token = decrypt_token(workspace.owner.github_token_encrypted)

        # Initialize services
        gh_actions = GitHubActionsService(github_token)
        api_key = plugin.resolve_api_key("anthropic") or settings.ANTHROPIC_API_KEY
        anthropic_client = Anthropic(api_key=api_key)

        # Step 1: Fetch and analyze CI logs
        logger.info(f"Fetching CI logs for run {ci_run.run_id}")
        run_status = gh_actions.get_workflow_run_status(ci_run.repository, ci_run.run_id)

        # For now, use check_results from webhook
        # In production, you'd download and parse actual logs
        error_analysis = analyze_ci_errors(ci_run, gh_actions)

        # Step 2: Build prompt for Claude
        prompt = build_self_fix_prompt(ci_run, error_analysis, workspace)

        # Step 3: Generate fixes using Claude
        logger.info(f"Requesting fixes from Claude for CI run {ci_run.id}")
        fix_response = await generate_fixes_with_claude(anthropic_client, prompt)

        # Step 4: Apply fixes to repository
        logger.info(f"Applying fixes for CI run {ci_run.id}")
        applied_fixes = await apply_fixes_to_repository(
            workspace=workspace,
            pr_number=ci_run.pr_number,
            branch_name=ci_run.branch_name,
            fixes=fix_response["fixes"],
            github_token=github_token,
            db=db
        )

        # Update CI run with success
        ci_run.self_fix_successful = True
        ci_run.error_summary = f"Self-fix applied: {fix_response['summary']}"
        db.commit()

        logger.info(f"Self-fix successful for CI run {ci_run.id}")

        result = {
            "success": True,
            "ci_run_id": ci_run.id,
            "retry_count": ci_run.retry_count,
            "fixes_applied": len(applied_fixes),
            "new_commit_sha": applied_fixes.get("commit_sha"),
            "summary": fix_response["summary"]
        }

        # Plugin: after_execute
        usage = ExecutionUsage(provider="anthropic", model="claude-sonnet-4-5-20250929")
        plugin.after_execute(ctx, result, usage)

        return result

    except Exception as e:
        plugin.on_execute_error(ctx, e)
        logger.error(f"Self-fix failed for CI run {ci_run.id}: {e}", exc_info=True)

        # Update CI run with failure
        ci_run.self_fix_successful = False
        ci_run.error_summary = f"Self-fix failed: {str(e)}"
        db.commit()

        # Create GitHub issue if max retries reached or critical failure
        should_create_issue = (
            ci_run.retry_count >= ci_run.max_retries or
            workspace.auto_create_issues  # Add config flag check
        )

        issue_result = None
        if should_create_issue:
            logger.info(
                f"Creating GitHub issue for CI run {ci_run.id} "
                f"(retry {ci_run.retry_count}/{ci_run.max_retries})"
            )
            try:
                # Reuse error_analysis from earlier in the function
                error_analysis = analyze_ci_errors(ci_run, gh_actions)
                issue_result = await create_github_issue_for_failure(
                    ci_run=ci_run,
                    error_analysis=error_analysis,
                    workspace=workspace,
                    github_token=github_token,
                    self_fix_error=str(e)
                )

                if issue_result.get("success"):
                    logger.info(
                        f"Created issue #{issue_result['issue_number']} for coding agent: "
                        f"{issue_result['issue_url']}"
                    )
            except Exception as issue_err:
                logger.error(f"Failed to create GitHub issue: {issue_err}", exc_info=True)

        return {
            "success": False,
            "ci_run_id": ci_run.id,
            "retry_count": ci_run.retry_count,
            "error": str(e),
            "issue_created": issue_result.get("success") if issue_result else False,
            "issue_number": issue_result.get("issue_number") if issue_result else None,
            "issue_url": issue_result.get("issue_url") if issue_result else None
        }


def analyze_ci_errors(ci_run: CIRun, gh_actions: GitHubActionsService) -> dict:
    """
    Analyze CI errors from check results and logs.

    Args:
        ci_run: CIRun object
        gh_actions: GitHub Actions service

    Returns:
        Dictionary with categorized errors
    """
    analysis = {
        "check_results": ci_run.check_results or {},
        "tests_failed": ci_run.tests_failed or 0,
        "lint_errors": ci_run.lint_errors_count or 0,
        "type_errors": ci_run.type_errors_count or 0,
        "error_categories": [],
        "parsed_errors": None,
        "error_summary": None
    }

    # Analyze check results
    if ci_run.check_results:
        for check_name, outcome in ci_run.check_results.items():
            if outcome != "success":
                analysis["error_categories"].append({
                    "check": check_name,
                    "outcome": outcome,
                    "severity": "high" if "test" in check_name.lower() else "medium"
                })

    # Try to fetch and parse actual logs if not already stored
    logs_to_parse = ci_run.raw_logs

    if not logs_to_parse:
        logger.info(f"Attempting to download logs for CI run {ci_run.id}, run_id: {ci_run.run_id}")
        try:
            # Download logs from GitHub
            logs_to_parse = gh_actions.get_job_logs(
                repo_name=ci_run.repository,
                run_id=ci_run.run_id,
                job_name=ci_run.job_name
            )

            if logs_to_parse:
                logger.info(f"Successfully downloaded {len(logs_to_parse)} characters of logs")
            else:
                logger.warning(f"No logs available for CI run {ci_run.id}")
        except Exception as e:
            logger.error(f"Failed to download logs for CI run {ci_run.id}: {e}")

    # Parse logs if available
    if logs_to_parse:
        try:
            parsed_errors = gh_actions.parse_workflow_logs(logs_to_parse)
            analysis["parsed_errors"] = parsed_errors
            analysis["error_summary"] = gh_actions.create_error_summary(parsed_errors)

            # Update test failure count from parsed logs if available
            if parsed_errors.get("test_failures"):
                analysis["tests_failed"] = len(parsed_errors["test_failures"])

            logger.info(
                f"Parsed logs for CI run {ci_run.id}: "
                f"{len(parsed_errors.get('test_failures', []))} test failures, "
                f"{len(parsed_errors.get('lint_errors', []))} lint errors, "
                f"{len(parsed_errors.get('type_errors', []))} type errors"
            )
        except Exception as e:
            logger.error(f"Failed to parse logs for CI run {ci_run.id}: {e}")

    return analysis


def build_self_fix_prompt(ci_run: CIRun, error_analysis: dict, workspace: Workspace) -> str:
    """
    Build comprehensive prompt for Claude to generate fixes.

    Args:
        ci_run: CIRun object
        error_analysis: Analyzed errors
        workspace: Workspace object

    Returns:
        Formatted prompt string
    """
    prompt = f"""You are an expert software engineer debugging a failed CI run. Your task is to analyze the errors and provide fixes.

## CI Run Information
- Repository: {ci_run.repository}
- PR Number: #{ci_run.pr_number}
- Branch: {ci_run.branch_name}
- Commit: {ci_run.commit_sha}
- Job: {ci_run.job_name}
- Status: {ci_run.status} / {ci_run.conclusion}

## Error Analysis
{json.dumps(error_analysis, indent=2)}

## Check Results
"""

    if ci_run.check_results:
        for check, outcome in ci_run.check_results.items():
            status_icon = "✅" if outcome == "success" else "❌"
            prompt += f"{status_icon} {check}: {outcome}\n"

    prompt += f"""
## Context
- This is retry attempt {ci_run.retry_count} of {ci_run.max_retries}
- Previous fixes have not resolved the issues
- You must provide working fixes that will pass CI

## Task
Analyze the failures and provide complete fixes. Your response must be valid JSON:

{{
  "analysis": "Brief analysis of what's wrong and your fix strategy",
  "summary": "One-line summary of fixes (e.g., 'Fixed 3 test failures and 2 lint errors')",
  "fixes": [
    {{
      "file": "path/to/file.py",
      "reason": "Why this file needs changes",
      "changes": [
        {{
          "type": "replace",
          "old_code": "exact code to replace",
          "new_code": "corrected code"
        }}
      ]
    }}
  ],
  "confidence": "high/medium/low"
}}

Guidelines:
1. Only fix what's broken - don't refactor unrelated code
2. Ensure fixes are minimal and targeted
3. Test failures: Fix the actual bugs, don't just modify tests
4. Lint errors: Fix code style issues
5. Type errors: Add proper type annotations
6. Import errors: Add missing imports or fix import paths
7. Build errors: Fix syntax or configuration issues

Provide complete, working fixes that will pass CI checks.
"""

    return prompt


async def generate_fixes_with_claude(client: Anthropic, prompt: str) -> dict:
    """
    Use Claude to generate fixes for CI failures.

    Args:
        client: Anthropic client
        prompt: Fix generation prompt

    Returns:
        Dictionary with fixes

    Raises:
        CISelfFixError: If Claude API call fails or response is invalid
    """
    try:
        message = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=8000,
            temperature=0.2,  # Lower temperature for more focused fixes
            messages=[{"role": "user", "content": prompt}]
        )

        # Extract text response
        response_text = message.content[0].text

        # Parse JSON response
        # Claude might wrap JSON in markdown code blocks
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()

        fix_data = json.loads(response_text)

        # Validate response structure
        required_keys = ["analysis", "summary", "fixes"]
        for key in required_keys:
            if key not in fix_data:
                raise CISelfFixError(f"Invalid Claude response: missing '{key}' field")

        logger.info(f"Claude generated {len(fix_data['fixes'])} fixes with confidence: {fix_data.get('confidence', 'unknown')}")

        return fix_data

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Claude response as JSON: {e}")
        logger.error(f"Response text: {response_text}")
        raise CISelfFixError(f"Invalid JSON response from Claude: {e}")

    except Exception as e:
        logger.error(f"Claude API call failed: {e}")
        raise CISelfFixError(f"Failed to generate fixes: {e}")


def build_issue_content(
    ci_run: CIRun,
    error_analysis: dict,
    self_fix_error: Optional[str] = None
) -> tuple[str, str]:
    """
    Build GitHub issue title and body for a CI failure.

    Args:
        ci_run: CIRun object that failed
        error_analysis: Analyzed errors from the CI run
        self_fix_error: Optional error message from self-fix attempt

    Returns:
        Tuple of (title, body)
    """
    # Build detailed issue description
    issue_title = f"CI Failure: {ci_run.job_name} failed on PR #{ci_run.pr_number}"

    issue_body = f"""## CI Run Failed
**Repository:** {ci_run.repository}
**PR Number:** #{ci_run.pr_number}
**Branch:** {ci_run.branch_name}
**Commit:** {ci_run.commit_sha}
**Run ID:** {ci_run.run_id}
**Job:** {ci_run.job_name}
**Status:** {ci_run.conclusion}

---

## Error Analysis

### Summary
- Tests Failed: {error_analysis.get('tests_failed', 0)}
- Lint Errors: {error_analysis.get('lint_errors', 0)}
- Type Errors: {error_analysis.get('type_errors', 0)}

### Check Results
"""

    # Add check results details
    check_results = error_analysis.get('check_results', {})
    for check_name, outcome in check_results.items():
        status_icon = "✅" if outcome == "success" else "❌"
        issue_body += f"{status_icon} **{check_name}**: {outcome}\n"

    # Add error categories
    if error_analysis.get('error_categories'):
        issue_body += "\n### Error Categories\n"
        for error_cat in error_analysis['error_categories']:
            issue_body += f"- **{error_cat['check']}**: {error_cat['outcome']} (severity: {error_cat['severity']})\n"

    # Add error summary if available
    if error_analysis.get('error_summary'):
        issue_body += f"\n### Detailed Errors\n```\n{error_analysis['error_summary']}\n```\n"

    # Add detailed test failures if available
    parsed_errors = error_analysis.get('parsed_errors')
    if parsed_errors:
        if parsed_errors.get('test_failures'):
            issue_body += "\n### Test Failures\n"
            for i, failure in enumerate(parsed_errors['test_failures'][:10], 1):  # Limit to first 10
                issue_body += f"\n{i}. `{failure['line']}`\n"
                if failure.get('context'):
                    issue_body += "   ```\n"
                    for ctx_line in failure['context'][:3]:  # Limit context
                        issue_body += f"   {ctx_line}\n"
                    issue_body += "   ```\n"

            if len(parsed_errors['test_failures']) > 10:
                issue_body += f"\n_...and {len(parsed_errors['test_failures']) - 10} more test failures_\n"

        if parsed_errors.get('lint_errors'):
            issue_body += "\n### Lint Errors\n"
            for i, error in enumerate(parsed_errors['lint_errors'][:5], 1):
                issue_body += f"{i}. `{error['line']}`\n"
            if len(parsed_errors['lint_errors']) > 5:
                issue_body += f"\n_...and {len(parsed_errors['lint_errors']) - 5} more lint errors_\n"

        if parsed_errors.get('type_errors'):
            issue_body += "\n### Type Errors\n"
            for i, error in enumerate(parsed_errors['type_errors'][:5], 1):
                issue_body += f"{i}. `{error['line']}`\n"
            if len(parsed_errors['type_errors']) > 5:
                issue_body += f"\n_...and {len(parsed_errors['type_errors']) - 5} more type errors_\n"

        if parsed_errors.get('import_errors'):
            issue_body += "\n### Import Errors\n"
            for error in parsed_errors['import_errors']:
                issue_body += f"- `{error['line']}`\n"

        if parsed_errors.get('syntax_errors'):
            issue_body += "\n### Syntax Errors\n"
            for error in parsed_errors['syntax_errors']:
                issue_body += f"- `{error['line']}`\n"

    # Add self-fix attempt info
    issue_body += f"\n---\n\n## Self-Fix Attempt\n"
    issue_body += f"- **Retry Count:** {ci_run.retry_count}/{ci_run.max_retries}\n"
    issue_body += f"- **Self-Fix Attempted:** {'Yes' if ci_run.self_fix_attempted else 'No'}\n"

    if self_fix_error:
        issue_body += f"- **Self-Fix Error:** {self_fix_error}\n"

    issue_body += f"\n---\n\n"
    issue_body += f"**Note:** This issue was automatically created by Avery. "
    issue_body += f"The `avery-developer` label will trigger the coding agent to attempt a fix.\n\n"
    issue_body += f"🔗 [View CI Run]({ci_run.run_id})\n"

    return issue_title, issue_body


async def create_github_issue_for_failure(
    ci_run: CIRun,
    error_analysis: dict,
    workspace: Workspace,
    github_token: str,
    self_fix_error: Optional[str] = None
) -> dict:
    """
    Create a GitHub issue with 'avery-developer' label for the coding agent to resolve.

    Args:
        ci_run: CIRun object that failed
        error_analysis: Analyzed errors from the CI run
        workspace: Workspace object
        github_token: GitHub access token
        self_fix_error: Optional error message from self-fix attempt

    Returns:
        Dictionary with issue creation result
    """
    try:
        # Build issue content
        issue_title, issue_body = build_issue_content(ci_run, error_analysis, self_fix_error)

        # Create the issue with avery-developer label
        git_provider = get_git_provider_for_workspace(workspace)
        result = git_provider.create_issue(
            token=github_token,
            repo=ci_run.repository,
            title=issue_title,
            body=issue_body,
            labels=["avery-developer", "ci-failure", "automated"]
        )

        if result["success"]:
            logger.info(
                f"Created GitHub issue #{result['issue_number']} for CI run {ci_run.id}: "
                f"{result['issue_url']}"
            )
        else:
            logger.error(f"Failed to create GitHub issue: {result['error']}")

        return result

    except Exception as e:
        logger.error(f"Error creating GitHub issue for CI run {ci_run.id}: {e}", exc_info=True)
        return {
            "success": False,
            "issue_number": None,
            "issue_url": None,
            "error": str(e)
        }


async def apply_fixes_to_repository(
    workspace: Workspace,
    pr_number: int,
    branch_name: str,
    fixes: list[dict],
    github_token: str,
    db: Session
) -> dict:
    """
    Apply fixes to repository and push to PR branch.

    Args:
        workspace: Workspace object
        pr_number: Pull request number
        branch_name: Branch name
        fixes: List of fixes to apply
        github_token: GitHub access token
        db: Database session

    Returns:
        Dictionary with applied fixes info

    Raises:
        CISelfFixError: If applying fixes fails
    """
    from app.services.git_local_service import ensure_repo_cloned, checkout_branch
    import os

    try:
        # Clone/update repository using provider-specific clone URL
        git_provider = get_git_provider_for_workspace(workspace)
        repo_path = f"{settings.REPOS_BASE_PATH}/workspace-{workspace.id}/ci-fix-{pr_number}"
        clone_url = git_provider.get_clone_url(workspace.github_repository, github_token)
        ensure_repo_cloned(
            repo_path=repo_path,
            repo_url=workspace.github_repository,
            token=github_token,
            auth_clone_url=clone_url
        )

        # Checkout PR branch
        checkout_branch(repo_path, branch_name)

        # Apply each fix
        applied_count = 0
        for fix in fixes:
            file_path = os.path.join(repo_path, fix["file"])

            if not os.path.exists(file_path):
                logger.warning(f"File not found: {fix['file']}, skipping")
                continue

            # Read current file content
            with open(file_path, "r") as f:
                content = f.read()

            # Apply changes
            for change in fix.get("changes", []):
                if change["type"] == "replace":
                    content = content.replace(
                        change["old_code"],
                        change["new_code"]
                    )

            # Write updated content
            with open(file_path, "w") as f:
                f.write(content)

            applied_count += 1
            logger.info(f"Applied fix to {fix['file']}")

        # Commit and push changes
        from subprocess import run

        commit_message = f"🤖 Agent CI self-fix: Applied {applied_count} fix(es) (retry {pr_number})"

        run(["git", "add", "."], cwd=repo_path, check=True)
        run(["git", "commit", "-m", commit_message], cwd=repo_path, check=True)
        run(["git", "push", "origin", branch_name], cwd=repo_path, check=True)

        # Get new commit SHA
        result = run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True
        )
        commit_sha = result.stdout.strip()

        logger.info(f"Pushed {applied_count} fixes to {branch_name}, commit: {commit_sha}")

        return {
            "applied_count": applied_count,
            "commit_sha": commit_sha,
            "commit_message": commit_message
        }

    except Exception as e:
        logger.error(f"Failed to apply fixes: {e}", exc_info=True)
        raise CISelfFixError(f"Failed to apply fixes to repository: {e}")
