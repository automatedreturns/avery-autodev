"""Coder Agent Service - Autonomous code generation using Claude API."""

import json
import logging
import re
from datetime import datetime

from anthropic import Anthropic

from app.core.config import settings
from app.engine.plugins import ExecutionContext, ExecutionUsage, get_plugin
from app.services.git_providers import get_git_provider
from app.services.git_providers.base import GitProvider

logger = logging.getLogger(__name__)


def _slugify(text: str, max_length: int = 50) -> str:
    """
    Convert text to a URL-safe slug.

    Args:
        text: Text to slugify
        max_length: Maximum length of slug

    Returns:
        Slugified text
    """
    # Convert to lowercase
    slug = text.lower()

    # Replace spaces and underscores with hyphens
    slug = re.sub(r'[\s_]+', '-', slug)

    # Remove non-alphanumeric characters except hyphens
    slug = re.sub(r'[^a-z0-9-]', '', slug)

    # Remove multiple consecutive hyphens
    slug = re.sub(r'-+', '-', slug)

    # Remove leading/trailing hyphens
    slug = slug.strip('-')

    # Truncate to max length
    if len(slug) > max_length:
        slug = slug[:max_length].rstrip('-')

    return slug


def _build_prompt(issue_details: dict, file_tree: list[dict], user_context: str, files_to_modify: list[str] | None) -> str:
    """
    Build the Claude prompt for code generation.

    Args:
        issue_details: GitHub issue details
        file_tree: Repository file structure
        user_context: Additional user-provided context
        files_to_modify: Optional list of specific files to modify

    Returns:
        Formatted prompt string
    """
    # Format file tree into a readable structure (limit to first 500 files)
    tree_summary = []
    for item in file_tree[:500]:
        if item["type"] == "blob":  # Only show files, not directories
            tree_summary.append(f"  {item['path']}")

    tree_str = "\n".join(tree_summary)
    if len(file_tree) > 500:
        tree_str += f"\n  ... and {len(file_tree) - 500} more files"

    # Build the prompt
    prompt = f"""You are an expert software engineer tasked with implementing a solution for a GitHub issue.

## GitHub Issue #{issue_details['number']}: {issue_details['title']}

**Description:**
{issue_details['body']}

**Labels:** {', '.join(issue_details['labels']) if issue_details['labels'] else 'None'}
**Status:** {issue_details['state']}

## Repository Structure
The repository contains the following files:
{tree_str}

## User Context
{user_context if user_context else 'No additional context provided.'}

## Files to Focus On
{', '.join(files_to_modify) if files_to_modify else 'No specific files specified. Choose the most appropriate files to modify.'}

## Task
Please analyze the issue and provide a complete implementation. Your response must be in the following JSON format:

{{
  "analysis": "Brief analysis of the issue and your approach (2-3 sentences)",
  "files": [
    {{
      "path": "relative/path/to/file.py",
      "content": "complete file content here",
      "reason": "why this file needs to be changed"
    }}
  ],
  "commit_message": "Concise commit message describing the changes",
  "pr_description": "Detailed PR description explaining the implementation"
}}

**Important Guidelines:**
1. Include COMPLETE file contents, not just diffs or snippets
2. Only include files that actually need to be modified
3. Keep changes focused on solving the specific issue
4. Follow the existing code style in the repository
5. Write clean, well-documented code
6. The commit message should be concise (50-72 characters)
7. The PR description should explain what was done and why

Please provide your response as valid JSON only, with no additional text before or after."""

    return prompt


def _parse_agent_response(response_text: str) -> dict:
    """
    Parse Claude's structured JSON response.

    Args:
        response_text: Raw response text from Claude

    Returns:
        Parsed response dict with keys: analysis, files, commit_message, pr_description

    Raises:
        ValueError: If response cannot be parsed
    """
    try:
        # Try to extract JSON from the response (in case there's extra text)
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if json_match:
            response_text = json_match.group(0)

        parsed = json.loads(response_text)

        # Validate required fields
        required_fields = ["analysis", "files", "commit_message", "pr_description"]
        for field in required_fields:
            if field not in parsed:
                raise ValueError(f"Missing required field: {field}")

        # Validate files structure
        if not isinstance(parsed["files"], list):
            raise ValueError("'files' must be a list")

        for file_obj in parsed["files"]:
            if not all(k in file_obj for k in ["path", "content", "reason"]):
                raise ValueError("Each file must have 'path', 'content', and 'reason'")

        return parsed

    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON response: {str(e)}")
    except Exception as e:
        raise ValueError(f"Failed to parse response: {str(e)}")


def execute_coder_agent(
    token: str,
    repo: str,
    base_branch: str,
    issue_number: int,
    user_context: str = "",
    files_to_modify: list[str] | None = None,
    git_provider: GitProvider | None = None,
    user_id: str | None = None,
    workspace_id: str | None = None,
) -> dict:
    """
    Execute the coder agent to automatically implement a solution for a GitHub issue.

    This is the main orchestration function that:
    1. Fetches issue details from GitHub
    2. Gets repository file structure
    3. Calls Claude API to generate code
    4. Creates a new branch
    5. Commits changes
    6. Creates a draft pull request

    Args:
        token: GitHub personal access token
        repo: Repository in format "owner/repo"
        base_branch: Branch to create from (e.g., "dev", "main")
        issue_number: GitHub issue number
        user_context: Additional context from user (optional)
        files_to_modify: Specific files to modify (optional)
        git_provider: Git provider instance (optional)
        user_id: User ID for plugin hooks (optional)
        workspace_id: Workspace ID for plugin hooks (optional)

    Returns:
        dict with execution result:
        {
            "success": bool,
            "branch_name": str | None,
            "pr_number": int | None,
            "pr_url": str | None,
            "error": str | None,
            "details": dict | None  # Additional execution details
        }
    """
    if git_provider is None:
        git_provider = get_git_provider("github")

    plugin = get_plugin()

    # Plugin: check access
    if user_id and not plugin.check_access(user_id, "agent_execute"):
        return {
            "success": False,
            "branch_name": None,
            "pr_number": None,
            "pr_url": None,
            "error": "Insufficient credits or access denied",
            "details": None,
        }

    # Plugin: before_execute
    ctx = ExecutionContext(
        action="agent_execute",
        user_id=user_id or "",
        workspace_id=workspace_id,
        metadata={"repo": repo, "issue_number": issue_number},
    )
    ctx = plugin.before_execute(ctx)

    try:
        # Step 1: Fetch issue details
        issue_details = git_provider.get_issue_details(token, repo, issue_number)
        if issue_details.get("error"):
            return {
                "success": False,
                "branch_name": None,
                "pr_number": None,
                "pr_url": None,
                "error": f"Failed to fetch issue: {issue_details['error']}",
                "details": None
            }

        # Step 2: Get repository file structure
        file_tree_result = git_provider.get_repository_tree(token, repo, base_branch)
        if file_tree_result.get("error"):
            return {
                "success": False,
                "branch_name": None,
                "pr_number": None,
                "pr_url": None,
                "error": f"Failed to fetch repository structure: {file_tree_result['error']}",
                "details": None
            }

        # Step 3: Build prompt and call Claude API
        prompt = _build_prompt(issue_details, file_tree_result["tree"], user_context, files_to_modify)

        try:
            # Plugin: resolve API key (falls back to settings)
            api_key = plugin.resolve_api_key("anthropic") or settings.ANTHROPIC_API_KEY
            client = Anthropic(api_key=api_key)
            message = client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=settings.AGENT_MAX_TOKENS,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            response_text = message.content[0].text

            # Track usage for plugin
            usage = ExecutionUsage(
                provider="anthropic",
                model="claude-sonnet-4-5-20250929",
                input_tokens=getattr(message.usage, "input_tokens", 0),
                output_tokens=getattr(message.usage, "output_tokens", 0),
                total_tokens=getattr(message.usage, "input_tokens", 0) + getattr(message.usage, "output_tokens", 0),
            )

        except Exception as e:
            plugin.on_execute_error(ctx, e)
            return {
                "success": False,
                "branch_name": None,
                "pr_number": None,
                "pr_url": None,
                "error": f"Claude API error: {str(e)}",
                "details": None
            }

        # Step 4: Parse Claude's response
        try:
            agent_response = _parse_agent_response(response_text)
        except ValueError as e:
            return {
                "success": False,
                "branch_name": None,
                "pr_number": None,
                "pr_url": None,
                "error": f"Failed to parse agent response: {str(e)}",
                "details": {"raw_response": response_text}
            }

        # Step 5: Create branch
        issue_slug = _slugify(issue_details["title"])
        branch_name = f"coder/issue-{issue_number}-{issue_slug}"

        branch_result = git_provider.create_branch(token, repo, branch_name, base_branch)
        if not branch_result["success"]:
            return {
                "success": False,
                "branch_name": branch_name,
                "pr_number": None,
                "pr_url": None,
                "error": f"Failed to create branch: {branch_result['error']}",
                "details": agent_response
            }

        # Step 6: Commit file changes
        commit_errors = []
        for file_obj in agent_response["files"]:
            file_path = file_obj["path"]
            file_content = file_obj["content"]

            # Get existing file SHA if it exists (needed for updates)
            existing_file = git_provider.get_file_content(token, repo, branch_name, file_path)
            file_sha = existing_file.get("sha")

            # Create or update the file
            commit_result = git_provider.create_or_update_file(
                token=token,
                repo=repo,
                branch=branch_name,
                file_path=file_path,
                content=file_content,
                message=agent_response["commit_message"],
                sha=file_sha
            )

            if not commit_result["success"]:
                commit_errors.append(f"{file_path}: {commit_result['error']}")

        if commit_errors:
            return {
                "success": False,
                "branch_name": branch_name,
                "pr_number": None,
                "pr_url": None,
                "error": f"Failed to commit changes: {'; '.join(commit_errors)}",
                "details": agent_response
            }

        # Step 7: Check for existing PR before creating a new one
        existing_pr_result = git_provider.find_pr_by_branch(
            token=token,
            repo=repo,
            head_branch=branch_name,
            base_branch=base_branch,
            state="all"
        )

        if existing_pr_result.get("error"):
            # Log warning but continue with PR creation attempt
            logger.warning(f"Error checking for existing PR: {existing_pr_result['error']}")

        if existing_pr_result.get("found"):
            existing_pr = existing_pr_result["pr"]
            pr_state = existing_pr["state"]
            pr_merged = existing_pr.get("merged", False)

            if pr_state == "open":
                # PR is open - return existing PR info and add a comment with latest changes
                pr_number = existing_pr["number"]

                # Add comment about new changes
                comment_body = f"""## 🤖 Agent Updated Implementation

The agent has pushed additional changes to this branch.

**Analysis:** {agent_response['analysis']}

**Files Changed:**
{chr(10).join(f'- `{f["path"]}`: {f["reason"]}' for f in agent_response['files'])}

---
*Automated update by Coder Agent*
"""
                git_provider.add_pr_comment(
                    token=token,
                    repo=repo,
                    pr_number=pr_number,
                    comment=comment_body
                )

                return {
                    "success": True,
                    "branch_name": branch_name,
                    "pr_number": pr_number,
                    "pr_url": existing_pr["html_url"],
                    "error": None,
                    "existing_pr": True,
                    "details": {
                        "analysis": agent_response["analysis"],
                        "files_changed": [f["path"] for f in agent_response["files"]],
                        "commit_message": agent_response["commit_message"],
                        "message": f"Updated existing open PR #{pr_number}"
                    }
                }

            elif pr_state == "closed" and pr_merged:
                # PR was merged - need to create a new branch and PR
                # Append timestamp to branch name to avoid conflict
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                new_branch_name = f"{branch_name}-{timestamp}"

                # Create new branch
                new_branch_result = git_provider.create_branch(token, repo, new_branch_name, base_branch)
                if not new_branch_result["success"]:
                    return {
                        "success": False,
                        "branch_name": new_branch_name,
                        "pr_number": None,
                        "pr_url": None,
                        "error": f"Previous PR was merged. Failed to create new branch: {new_branch_result['error']}",
                        "details": agent_response
                    }

                # Commit to new branch
                for file_obj in agent_response["files"]:
                    file_path = file_obj["path"]
                    file_content = file_obj["content"]
                    existing_file = git_provider.get_file_content(token, repo, new_branch_name, file_path)
                    file_sha = existing_file.get("sha")

                    commit_result = git_provider.create_or_update_file(
                        token=token,
                        repo=repo,
                        branch=new_branch_name,
                        file_path=file_path,
                        content=file_content,
                        message=agent_response["commit_message"],
                        sha=file_sha
                    )
                    if not commit_result["success"]:
                        return {
                            "success": False,
                            "branch_name": new_branch_name,
                            "pr_number": None,
                            "pr_url": None,
                            "error": f"Failed to commit to new branch: {commit_result['error']}",
                            "details": agent_response
                        }

                branch_name = new_branch_name  # Use new branch for PR creation

            # For closed (not merged) PRs, we create a fresh PR on the same branch

        # Create pull request
        pr_title = f"Fix #{issue_number}: {issue_details['title']}"
        pr_body = f"""{agent_response['pr_description']}

---

**Automated PR created by Coder Agent**

Fixes #{issue_number}

**Analysis:** {agent_response['analysis']}

**Files Changed:**
{chr(10).join(f'- `{f["path"]}`: {f["reason"]}' for f in agent_response['files'])}
"""

        pr_result = git_provider.create_pull_request(
            token=token,
            repo=repo,
            head=branch_name,
            base=base_branch,
            title=pr_title,
            body=pr_body,
            draft=True
        )

        if not pr_result["success"]:
            return {
                "success": False,
                "branch_name": branch_name,
                "pr_number": None,
                "pr_url": None,
                "error": f"Failed to create PR: {pr_result['error']}",
                "details": agent_response
            }

        # Success!
        result = {
            "success": True,
            "branch_name": branch_name,
            "pr_number": pr_result["pr_number"],
            "pr_url": pr_result["pr_url"],
            "error": None,
            "existing_pr": False,
            "details": {
                "analysis": agent_response["analysis"],
                "files_changed": [f["path"] for f in agent_response["files"]],
                "commit_message": agent_response["commit_message"]
            }
        }

        # Plugin: after_execute
        plugin.after_execute(ctx, result, usage)

        return result

    except Exception as e:
        plugin.on_execute_error(ctx, e)
        return {
            "success": False,
            "branch_name": None,
            "pr_number": None,
            "pr_url": None,
            "error": f"Unexpected error: {str(e)}",
            "details": None
        }
