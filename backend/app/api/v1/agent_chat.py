"""Agent Chat API endpoints for interactive conversation with the coder agent."""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from anthropic import Anthropic

logger = logging.getLogger(__name__)

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.permissions import get_workspace_or_403
from app.database import get_db
from app.models.agent_message import AgentMessage
from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspace_task import WorkspaceTask
from app.schemas.agent_message import (
    AgentMessageCreate,
    AgentMessageListResponse,
    AgentMessageResponse,
)
from app.services.workspace_token_service import get_workspace_github_token_or_403
from app.services import git_local_service
from app.services.git_providers import get_git_provider_for_workspace
from app.services.coder_agent_service import _slugify
from app.services.agent_tool_manager import get_tool_manager
from app.services.agent_tools.validation_pipeline import (
    ValidationPipeline,
    format_validation_message
)

router = APIRouter()

# Token limit constants for prompt components
MAX_ISSUE_BODY_TOKENS = 4000
MAX_FILE_TREE_TOKENS = 3000
MAX_ATTACHMENTS_TOKENS = 5000
MAX_TOTAL_CONTEXT_TOKENS = 180000  # Leave room for response
MAX_COMPACTION_RETRIES = 2  # How many times to retry after compaction
MAX_ITERATION_RESUME_RETRIES = 2  # How many times to auto-resume after hitting max iterations
INITIAL_MAX_TURNS = 100  # Initial max turns for agent SDK
RESUME_MAX_TURNS = 75  # Max turns for continuation/resume runs


def _truncate_to_token_limit(text: str, max_tokens: int, suffix: str = "\n...(truncated)") -> str:
    """
    Truncate text to approximate token limit.

    Uses a rough estimate of ~4 characters per token for Claude models.

    Args:
        text: Text to truncate
        max_tokens: Maximum tokens allowed
        suffix: Suffix to append when truncated

    Returns:
        Original text if within limit, otherwise truncated text with suffix
    """
    if not text:
        return text
    estimated_chars = max_tokens * 4  # ~4 chars per token for Claude
    if len(text) <= estimated_chars:
        return text
    return text[:estimated_chars - len(suffix)] + suffix


def _estimate_tokens(text: str) -> int:
    """Estimate token count for text (~4 chars per token for Claude)."""
    return len(text) // 4 if text else 0


async def _compact_conversation_context(
    db: Session,
    task_id: int,
    workspace: "Workspace",
    task: "WorkspaceTask",
    issue_details: dict
) -> str:
    """
    Compact the conversation history into a summary for context continuity.

    This is called when the prompt becomes too long. It:
    1. Fetches recent conversation messages
    2. Uses Claude to summarize the conversation and work done
    3. Returns a compact summary to use in a fresh session

    Args:
        db: Database session
        task_id: Task ID
        workspace: Workspace object
        task: WorkspaceTask object
        issue_details: GitHub issue details

    Returns:
        Compact summary string to use as context for new session
    """
    # Get conversation history
    history = (
        db.query(AgentMessage)
        .filter(AgentMessage.workspace_task_id == task_id)
        .order_by(AgentMessage.created_at.asc())
        .all()
    )

    if not history:
        return ""

    # Build conversation text for summarization (limit to last 50 messages)
    recent_messages = history[-50:]
    conversation_text = []
    for msg in recent_messages:
        role = msg.role.upper()
        content = msg.content or ""
        # Truncate individual messages to avoid oversized summarization request
        if len(content) > 2000:
            content = content[:2000] + "...(truncated)"
        conversation_text.append(f"{role}: {content}")

    conversation_str = "\n\n".join(conversation_text)

    # Use Claude to create a summary
    try:
        client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)

        summary_prompt = f"""You are summarizing a coding session for context continuity. The conversation context has grown too large and needs to be compacted.

Issue: #{task.github_issue_number} - {issue_details.get('title', 'Unknown')}
Repository: {workspace.github_repository}
Branch: {task.agent_branch_name}

CONVERSATION HISTORY:
{conversation_str}

Please provide a CONCISE summary (max 1500 words) covering:
1. **Work Completed**: What files were created/modified and what changes were made
2. **Current State**: Where the implementation currently stands
3. **Pending Items**: Any known issues or tasks still to be done
4. **Key Decisions**: Important technical decisions made during the session

Keep the summary factual and focused on code changes. This will be used to continue the session."""

        response = client.messages.create(
            model="claude-sonnet-4-20250514",  # Use faster model for summarization
            max_tokens=2000,
            messages=[{"role": "user", "content": summary_prompt}]
        )

        summary = response.content[0].text if response.content else ""
        return summary

    except Exception as e:
        logger.warning(f"Failed to create conversation summary for task {task_id}: {e}")
        # Fallback: just return a basic summary of the task state
        return f"""Previous session context (auto-generated fallback):
- Working on issue #{task.github_issue_number}
- Branch: {task.agent_branch_name}
- Status: {task.agent_status}
- The conversation was compacted due to context length limits.
Please continue from where the previous session left off."""


def _reset_session_for_compaction(db: Session, task: "WorkspaceTask") -> None:
    """
    Reset the Claude session ID to start a fresh session after compaction.

    Args:
        db: Database session
        task: WorkspaceTask to reset
    """
    task.claude_session_id = None
    db.commit()
    logger.info(f"Reset Claude session for task {task.id} due to context compaction")


def apply_path_masking(mask_path, file_path):
    if not mask_path:
        return file_path
    return file_path.replace(mask_path, "")

def _format_tool_display(tool_name: str, tool_input: dict, mask_path: str = None) -> str:
    """
    Format tool execution for user display.

    Handles both SDK built-in tools (Read, Write, Edit, Bash, Glob, Grep)
    and custom MCP tools (search_code, run_tests, etc.).
    """
    # SDK Built-in Tools
    if tool_name == "Read":
        file_path = tool_input.get('file_path', '')
        file_path = apply_path_masking(mask_path, file_path)
        offset = tool_input.get('offset')
        limit = tool_input.get('limit')
        if offset is not None and limit is not None:
            return f"Reading {file_path} (lines {offset}-{offset+limit})"
        return f"Reading {file_path}"

    elif tool_name == "Write":
        file_path = tool_input.get('file_path', '')
        file_path = apply_path_masking(mask_path, file_path)
        return f"Writing file: {file_path}"

    elif tool_name == "Edit":
        file_path = tool_input.get('file_path', '')
        file_path = apply_path_masking(mask_path, file_path)
        return f"Editing file: {file_path}"

    elif tool_name == "Bash":
        command = tool_input.get('command', '')
        command = apply_path_masking(mask_path, command)
        # Truncate long commands
        display_cmd = command[:60] + "..." if len(command) > 60 else command
        return f"Running: {display_cmd}"

    elif tool_name == "Glob":
        pattern = tool_input.get('pattern', '')
        path = tool_input.get('path', '.')
        if path and path != '.':
            path = apply_path_masking(mask_path, path)
            return f"Finding files: {pattern} in {path}"
        return f"Finding files: {pattern}"

    elif tool_name == "Grep":
        pattern = tool_input.get('pattern', '')
        path = tool_input.get('path', '')
        glob_filter = tool_input.get('glob', '')
        if path:
            path = apply_path_masking(mask_path, path)
            return f"Searching in {path}: {pattern}"
        elif glob_filter:
            return f"Searching {glob_filter}: {pattern}"
        return f"Searching for: {pattern}"

    # Custom MCP Tools
    elif tool_name == "search_code":
        pattern = tool_input.get('pattern', '')
        return f"Searching for: {pattern}"
    elif tool_name == "find_definition":
        symbol = tool_input.get('symbol', '')
        return f"Finding definition of: {symbol}"
    elif tool_name == "find_references":
        symbol = tool_input.get('symbol', '')
        return f"Finding references to: {symbol}"
    elif tool_name == "run_tests":
        path = tool_input.get('test_path', 'all tests')
        return f"Running tests: {path}"
    elif tool_name == "run_build":
        return "Building project..."
    elif tool_name == "run_linter":
        return "Running linter..."
    elif tool_name == "type_check":
        return "Type checking..."
    elif tool_name == "get_git_diff":
        file_path = tool_input.get('file_path')
        return f"Getting git diff{f' for {file_path}' if file_path else '...'}"
    elif tool_name == "git_status":
        return "Getting git status..."
    elif tool_name == "install_dependencies":
        packages = tool_input.get('packages', [])
        return f"Installing: {', '.join(packages[:3])}{'...' if len(packages) > 3 else ''}"
    elif tool_name == "check_dependencies":
        return "Checking dependencies..."
    elif tool_name == "get_file_symbols":
        file_path = tool_input.get('file_path', '')
        return f"Analyzing: {file_path}"
    elif tool_name == "read_file_range":
        file_path = tool_input.get('file_path', '')
        start = tool_input.get('start_line', 0)
        end = tool_input.get('end_line', 0)
        return f"Reading {file_path} lines {start}-{end}"

    # Fallback for unknown tools
    else:
        return f"{tool_name}"


async def save_uploaded_file(workspace_id: int, task_id: int, message_id: int, file: UploadFile) -> dict:
    """
    Save an uploaded file and return its metadata.

    Returns dict with: filename, file_path, file_size, content_type
    """
    # Create uploads directory structure: uploads/workspace-{id}/task-{id}/message-{id}/
    upload_dir = Path(settings.REPOS_BASE_PATH).parent / "uploads" / f"workspace-{workspace_id}" / f"task-{task_id}" / f"message-{message_id}"
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Generate unique filename to avoid conflicts
    file_extension = Path(file.filename or "file").suffix
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = upload_dir / unique_filename

    # Save file
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    return {
        "filename": file.filename or "unknown",
        "file_path": str(file_path),
        "file_size": len(content),
        "content_type": file.content_type or "application/octet-stream"
    }


@router.get(
    "/{workspace_id}/tasks/{task_id}/chat/messages",
    response_model=AgentMessageListResponse,
)
def list_chat_messages(
    workspace_id: int,
    task_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    skip: int = 0,
    limit: int = 1000,  # Increased from 100 to handle tasks with many progress messages
):
    """
    List all chat messages for a task.

    Args:
        workspace_id: Workspace ID
        task_id: Task ID
        db: Database session
        current_user: Current authenticated user
        skip: Number of records to skip
        limit: Maximum number of records to return

    Returns:
        List of chat messages

    Raises:
        HTTPException: If user is not a workspace member or task not found
    """
    workspace, _ = get_workspace_or_403(workspace_id, db, current_user)

    # Get task
    task = (
        db.query(WorkspaceTask)
        .filter(WorkspaceTask.id == task_id, WorkspaceTask.workspace_id == workspace_id)
        .first()
    )

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found in this workspace",
        )

    # Query messages with user details
    messages_query = (
        db.query(AgentMessage, User)
        .outerjoin(User, AgentMessage.user_id == User.id)
        .filter(AgentMessage.workspace_task_id == task_id)
        .order_by(AgentMessage.created_at.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    messages = []
    for message, user in messages_query:
        # Parse attachments from JSON
        attachments = None
        if message.attachments:
            try:
                attachments = json.loads(message.attachments)
            except (json.JSONDecodeError, TypeError):
                attachments = None

        messages.append(
            AgentMessageResponse(
                id=message.id,
                workspace_task_id=message.workspace_task_id,
                role=message.role,
                content=message.content,
                attachments=attachments,
                created_at=message.created_at,
                user_id=message.user_id,
                username=user.username if user else None,
            )
        )

    total = db.query(AgentMessage).filter(AgentMessage.workspace_task_id == task_id).count()

    return AgentMessageListResponse(messages=messages, total=total)


def _save_progress_message(db: Session, task_id: int, content: str) -> None:
    """Save a progress/status message to inform the user."""
    progress_msg = AgentMessage(
        workspace_task_id=task_id,
        role="system",
        content=content,
        user_id=None,
    )
    db.add(progress_msg)
    db.commit()


def _create_pull_request_automatically(
    db: Session,
    workspace: Workspace,
    task: WorkspaceTask,
    token: str,
    issue_details: dict,
    agent_summary: str | None = None
) -> dict:
    """
    Automatically create a pull request for a completed task.

    NOW INCLUDES: Test policy enforcement before PR creation.

    Args:
        db: Database session
        workspace: Workspace object
        task: WorkspaceTask object
        token: GitHub token
        issue_details: Issue details from GitHub
        agent_summary: Optional summary from agent messages to post as PR comment

    Returns:
        dict with success, pr_number, pr_url, or error
        OR dict with success=False, policy_violations if policies fail
    """
    from app.services.pre_pr_policy_service import PrePRPolicyService

    git_provider = get_git_provider_for_workspace(workspace)

    try:
        # Verify task has a branch
        if not task.agent_branch_name:
            return {
                "success": False,
                "error": "No branch created for this task"
            }

        # ============================================================
        # CHECK FOR EXISTING PR (not just in local task record)
        # ============================================================
        existing_pr_result = git_provider.find_pr_by_branch(
            token=token,
            repo=workspace.github_repository,
            head_branch=task.agent_branch_name,
            base_branch=workspace.github_dev_branch,
            state="all"
        )

        if existing_pr_result.get("found"):
            existing_pr = existing_pr_result["pr"]
            pr_state = existing_pr["state"]
            pr_merged = existing_pr.get("merged", False)

            if pr_state == "open":
                # PR is already open - update task record and add comment with latest changes
                pr_number = existing_pr["number"]
                pr_url = existing_pr["html_url"]

                # Update task with existing PR info if not already set
                if not task.agent_pr_number:
                    task.agent_pr_number = pr_number
                    task.agent_pr_url = pr_url
                    db.commit()

                # Add comment about new changes if agent_summary is provided
                if agent_summary:
                    comment_body = f"""## 🤖 Agent Updated Implementation

{agent_summary}

---
*This update was automatically posted by the Avery coding agent*
"""
                    git_provider.add_pr_comment(
                        token=token,
                        repo=workspace.github_repository,
                        pr_number=pr_number,
                        comment=comment_body
                    )

                # Fetch latest comments on the PR for context
                comments_result = git_provider.get_pr_comments(
                    token=token,
                    repo=workspace.github_repository,
                    pr_number=pr_number
                )

                return {
                    "success": True,
                    "pr_number": pr_number,
                    "pr_url": pr_url,
                    "existing_pr": True,
                    "message": f"Found existing open PR #{pr_number}. Added comment with latest changes.",
                    "latest_comments": comments_result.get("comments", [])[-5:] if comments_result.get("comments") else []
                }

            elif pr_state == "closed":
                task.agent_pr_number = None
                task.agent_pr_url = None
                db.commit()

        # If task already has PR number in local record but not found on GitHub, reset it
        elif task.agent_pr_number:
            # The PR recorded in task doesn't exist on GitHub anymore
            # This could happen if PR was deleted - allow creating a new one
            task.agent_pr_number = None
            task.agent_pr_url = None
            db.commit()

        # ============================================================
        # ENFORCE TEST POLICIES BEFORE PR CREATION
        # ============================================================
        policy_check_result = None
        if task.local_repo_path and workspace.test_policy_enabled:
            logger.info("Test policy enabled - collecting coverage and enforcing policies")

            # Collect coverage from repository
            coverage_data = PrePRPolicyService.collect_coverage(
                task.local_repo_path,
                workspace
            )

            if coverage_data:
                # Get current commit SHA and branch
                import subprocess
                try:
                    commit_sha = subprocess.check_output(
                        ["git", "rev-parse", "HEAD"],
                        cwd=task.local_repo_path,
                        text=True
                    ).strip()
                except (subprocess.CalledProcessError, FileNotFoundError, OSError):
                    commit_sha = "unknown"

                # Enforce policies
                should_create_pr, policy_decision, snapshot_id = PrePRPolicyService.enforce_policies_before_pr(
                    db=db,
                    workspace=workspace,
                    task=task,
                    coverage_data=coverage_data,
                    commit_sha=commit_sha,
                    branch_name=task.agent_branch_name
                )

                if not should_create_pr:
                    # Policies failed - block PR creation
                    violation_message = PrePRPolicyService.format_policy_violations_for_user(policy_decision)

                    return {
                        "success": False,
                        "error": "Test policy violations detected",
                        "policy_violations": policy_decision.get("violations", []),
                        "policy_warnings": policy_decision.get("warnings", []),
                        "violation_message": violation_message,
                        "coverage_percent": coverage_data.get("coverage_percent", 0.0)
                    }

                # Store policy check result for later (to add as PR comment)
                if policy_decision:
                    policy_check_result = {
                        "decision": policy_decision,
                        "coverage_percent": coverage_data.get("coverage_percent", 0.0)
                    }
            else:
                logger.warning("Could not collect coverage - proceeding with PR creation")
        # ============================================================
        # END OF NEW POLICY ENFORCEMENT CODE
        # ============================================================

        # Build PR title and body
        pr_title = f"Fix #{task.github_issue_number}: {issue_details.get('title', 'Automated fix')}"

        pr_body = f"""## Automated Implementation

This PR was automatically created by the Avery coding agent to resolve issue #{task.github_issue_number}.

### Issue Description
{issue_details.get('body', 'No description provided')}

### Changes
The agent has implemented the necessary changes to address this issue. Please review the commits in this PR for details.

### Branch
- **Source**: {task.agent_branch_name}
- **Target**: {workspace.github_dev_branch}

---
🤖 *Generated automatically by [Avery Agent](https://goodgist.com)*
"""

        # Create PR via GitHub API
        pr_result = git_provider.create_pull_request(
            token=token,
            repo=workspace.github_repository,
            title=pr_title,
            body=pr_body,
            head=task.agent_branch_name,
            base=workspace.github_dev_branch,
            draft=False  # Not a draft for automated PRs
        )

        if pr_result.get("error"):
            return {
                "success": False,
                "error": pr_result["error"]
            }

        # Update task with PR info
        pr_number = pr_result.get("pr_number")
        pr_url = pr_result.get("pr_url")
        task.agent_pr_number = pr_number
        task.agent_pr_url = pr_url
        db.commit()

        # Post agent summary as PR comment if available
        if agent_summary and pr_number:
            comment_body = f"""## 🤖 Agent Implementation Summary

{agent_summary}

---
*This summary was automatically generated by the Avery coding agent*
"""
            comment_result = git_provider.add_pr_comment(
                token=token,
                repo=workspace.github_repository,
                pr_number=pr_number,
                comment=comment_body
            )

            if not comment_result.get("success"):
                logger.warning(f"Failed to post PR comment: {comment_result.get('error')}")
                # Don't fail the entire PR creation if comment fails

        # NEW: Post policy check results as PR comment if there were warnings
        if policy_check_result and policy_check_result["decision"].get("warnings"):
            policy_comment = PrePRPolicyService.format_policy_comment_for_pr(
                policy_check_result["decision"],
                policy_check_result["coverage_percent"]
            )
            git_provider.add_pr_comment(
                token=token,
                repo=workspace.github_repository,
                pr_number=pr_number,
                comment=policy_comment
            )

        return {
            "success": True,
            "pr_number": pr_number,
            "pr_url": pr_url,
            "policy_check": policy_check_result
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e)
        }

async def _process_agent_response_async(
    workspace_id: int,
    task_id: int,
    user_message_id: int,
    token: str,
) -> None:
    """
    Process agent response using Claude Agent SDK.

    This replaces the manual tool loop with SDK's built-in agent execution.
    Preserves all critical functionality:
    - Progress message tracking
    - Conversation history management
    - Validation pipeline
    - Automatic PR creation
    """
    from app.database import SessionLocal
    from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
    import json
    from dataclasses import dataclass, is_dataclass, asdict

    db = SessionLocal()

    try:
        # KEEP: Setup logic (lines 310-448 from original)
        workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
        task = db.query(WorkspaceTask).filter(WorkspaceTask.id == task_id).first()

        if not workspace or not task:
            return

        git_provider = get_git_provider_for_workspace(workspace)

        # Get issue details
        issue_details = git_provider.get_issue_details(
            token, workspace.github_repository, task.github_issue_number
        )
        is_automated = "avery-developer" in [label.lower() for label in issue_details.get("labels", [])]

        # Always use automated workflow (per migration plan)
        _save_progress_message(db, task_id, "🚀 **Agent Started**\n\nAnalyzing issue and planning implementation...")

        # Ensure repository exists
        repo_path = task.local_repo_path
        if not repo_path or not Path(repo_path).exists():
            error_msg = AgentMessage(
                workspace_task_id=task_id,
                role="system",
                content="Error: Repository not initialized. Please try again.",
                user_id=None,
            )
            db.add(error_msg)
            db.commit()
            return

        # Get conversation history
        history = (
            db.query(AgentMessage)
            .filter(AgentMessage.workspace_task_id == task_id)
            .order_by(AgentMessage.created_at.asc())
            .all()
        )

        # Build prompt string for SDK
        # The SDK query() expects a single string prompt (the user's latest message)
        user_messages = [msg.content for msg in history if msg.role == "user" and msg.content]
        prompt_string = user_messages[-1] if user_messages else "Please help implement the solution."

        # Process attachments if not already processed
        if not task.attachments_metadata:
            _save_progress_message(db, task_id, "📎 Processing attachments...")
            try:
                from app.services.document_processor_service import document_processor

                issue_body = issue_details.get("body", "")
                attachment_results = await document_processor.process_issue_attachments(
                    workspace_task_id=task_id,
                    issue_body=issue_body,
                    github_token=token,
                    workspace_id=workspace_id,
                    task_id=task_id,
                    db=db
                )

                task.attachments_metadata = json.dumps(attachment_results)
                task.attachments_processed_at = datetime.utcnow()
                db.commit()

                _save_progress_message(db, task_id, "✅ Attachment processing completed!")
            except Exception as e:
                _save_progress_message(db, task_id, "⚠️ Error processing attachments!")

        # Get repository tree
        try:
            file_tree_summary = git_local_service.get_file_tree(repo_path, max_depth=3)
        except git_local_service.GitLocalError:
            file_tree_summary = "Unable to load file tree"

        # Truncate large components to prevent "Prompt is too long" errors
        issue_body = _truncate_to_token_limit(
            issue_details.get('body', 'No description'),
            MAX_ISSUE_BODY_TOKENS
        )
        file_tree_summary = _truncate_to_token_limit(
            file_tree_summary,
            MAX_FILE_TREE_TOKENS
        )
        attachments_context = _truncate_to_token_limit(
            _get_attachments_context(task),
            MAX_ATTACHMENTS_TOKENS
        )

        # Build system message (automated workflow only)
        system_message = f"""You are an expert software engineer helping to implement a solution for GitHub issue #{task.github_issue_number}.

Issue Title: {issue_details.get('title', 'N/A')}
Issue Description: {issue_body}
Labels: {', '.join(issue_details.get('labels', []))}

{attachments_context}

Repository: {workspace.github_repository}
Working Branch: {task.agent_branch_name}

Repository Structure (sample):
{file_tree_summary}

AUTOMATED WORKFLOW MODE:
You have FULL AUTONOMY to implement the solution.

YOUR WORKFLOW:
1. Use search_code and find_definition to locate relevant code quickly
2. Read necessary files to understand the codebase
3. Implement changes using Write or Edit tools (auto-commits)
4. Run validations: run_tests(), run_build(), run_linter()
5. When validations pass, end your response with: "IMPLEMENTATION_COMPLETE"

AVAILABLE TOOLS:

SDK Built-in Tools:
- Read: Read file contents (with offset/limit support)
- Write: Create new files (auto-commits and pushes)
- Edit: Modify existing files with precise edits (preferred over Write)
- Bash: Run terminal commands (git, build, tests)
- Glob: Find files by pattern (e.g., "**/*.py")
- Grep: Search code for patterns

Custom Tools (via MCP):
- search_code: Find patterns across the codebase (faster than Grep for complex searches)
- find_definition: Locate function/class definitions
- find_references: Find all usages of a symbol (essential before refactoring)
- get_file_symbols: Get overview of file structure without reading it all
- read_file_range: Read specific line ranges
- run_tests: Execute project tests (REQUIRED before IMPLEMENTATION_COMPLETE)
- run_build: Build/compile project (REQUIRED before IMPLEMENTATION_COMPLETE)
- run_linter: Check code quality (REQUIRED before IMPLEMENTATION_COMPLETE)
- type_check: Verify type safety
- get_git_diff: Review changes
- git_status: See repository status
- install_dependencies: Add packages if needed
- check_dependencies: Check for outdated/vulnerable packages

CRITICAL VALIDATION REQUIREMENTS:
Before marking IMPLEMENTATION_COMPLETE, you MUST:
1. Run tests: run_tests()
2. Run build: run_build()
3. Run linter: run_linter()

The system will automatically validate when you say IMPLEMENTATION_COMPLETE. If validation fails, you must fix the issues.

IMPORTANT:
- ALWAYS use search_code or Grep to find code instead of guessing file locations
- Prefer Edit over Write for modifying existing files
- Each Write/Edit operation auto-commits and pushes to the branch
- Make changes autonomously - no approval needed
"""
        # NEW: Use SDK query() instead of manual tool loop
        _save_progress_message(db, task_id, "🤖 Agent executing with Claude Agent SDK...")

        assistant_content = ""
        compacted_summary = None
        iteration_resume_count = 0
        current_max_turns = INITIAL_MAX_TURNS

        # Outer loop: auto-resume when agent runs out of max iterations
        while iteration_resume_count <= MAX_ITERATION_RESUME_RETRIES:
            compaction_retry_count = 0
            run_state = {"hit_max_iterations": False, "num_turns": 0, "max_turns": current_max_turns}
            run_content = ""

            # Inner loop: retry with context compaction on "prompt too long" errors
            while compaction_retry_count <= MAX_COMPACTION_RETRIES:
                try:
                    # Build system message - include compacted summary if this is a retry/resume
                    effective_system_message = system_message
                    if compacted_summary:
                        effective_system_message = f"""{system_message}

=== PREVIOUS SESSION SUMMARY (Context was compacted due to length) ===
{compacted_summary}
=== END OF PREVIOUS SESSION SUMMARY ===

Continue from where the previous session left off. The user's new message follows."""

                    # Create ClaudeAgentOptions with resume support for conversation continuation
                    # Don't resume if we just compacted (start fresh session with summary)
                    should_resume = task.claude_session_id if (task.claude_session_id and not compacted_summary) else None

                    agent_options = ClaudeAgentOptions(
                        system_prompt=effective_system_message,
                        model="claude-opus-4-6",
                        allowed_tools=[
                            # SDK built-ins
                            "Read",
                            "Write",
                            "Edit",
                            "Bash",
                            "Glob",
                            "Grep",
                            "TodoWrite",
                            "Task"
                        ],
                        max_turns=current_max_turns,
                        permission_mode="acceptEdits",  # Auto-approve edits
                        cwd=repo_path,
                        # Resume from previous session if one exists (enables conversation continuation)
                        resume=should_resume,
                        env={
                            "ANTHROPIC_API_KEY": settings.ANTHROPIC_API_KEY,  # Required for SDK subprocess
                            "branch": task.agent_branch_name,
                            "workspace_id": str(workspace_id),
                            "task_id": str(task_id),
                            "repo_path": repo_path
                        }
                    )

                    # Call SDK with streaming
                    if should_resume:
                        logger.debug(f"Resuming SDK session {task.claude_session_id} for task {task_id}")
                        _save_progress_message(db, task_id, "🔄 Resuming previous conversation session...")
                    elif compacted_summary:
                        logger.debug(f"Starting fresh SDK session with compacted context for task {task_id}")
                        _save_progress_message(db, task_id, "🔄 Starting fresh session with compacted context...")
                    else:
                        logger.debug(f"Starting new SDK session for task {task_id}")
                    logger.debug(f"Starting SDK query for task {task_id} (max_turns={current_max_turns}) with prompt: {prompt_string[:100]}...")
                    _save_progress_message(db, task_id, "🔍 Querying Claude Agent SDK...")

                    _client = ClaudeSDKClient(options=agent_options)
                    async with _client as client:
                        await client.query(prompt_string)

                        async for message in client.receive_response():
                            updated_task = db.query(WorkspaceTask).filter(WorkspaceTask.id == task_id).first()
                            if updated_task.agent_status == "cancelled":
                                await client.interrupt()
                                break

                            response_text = _process_message(message, db, task_id, repo_path, run_state)
                            if response_text:
                                run_content += response_text

                    # Success - break out of compaction retry loop
                    break

                except Exception as e:
                    import traceback
                    error_str = str(e).lower()
                    logger.error(f"SDK query failed: {str(e)}")
                    logger.error(traceback.format_exc())

                    # Check for context/prompt length errors
                    is_context_error = any(keyword in error_str for keyword in [
                        "too long", "context", "token limit", "maximum context",
                        "prompt is too long", "request too large", "content too large"
                    ])

                    if is_context_error and compaction_retry_count < MAX_COMPACTION_RETRIES:
                        # Attempt auto-compaction and retry
                        compaction_retry_count += 1
                        _save_progress_message(
                            db, task_id,
                            f"⚠️ **Context too long - Auto-compacting conversation...** (attempt {compaction_retry_count}/{MAX_COMPACTION_RETRIES})\n\n"
                            "The conversation history has grown too large. Automatically creating a summary and starting a fresh session."
                        )

                        # Perform compaction
                        try:
                            compacted_summary = await _compact_conversation_context(
                                db, task_id, workspace, task, issue_details
                            )
                            # Reset session ID to start fresh
                            _reset_session_for_compaction(db, task)

                            _save_progress_message(
                                db, task_id,
                                "✅ **Context compacted successfully**\n\nRetrying with fresh session..."
                            )
                            # Continue to next iteration of compaction retry loop
                            continue

                        except Exception as compact_error:
                            logger.error(f"Failed to compact context for task {task_id}: {compact_error}")
                            _save_progress_message(
                                db, task_id,
                                f"❌ **Auto-compaction failed**\n\n"
                                f"Could not automatically compact the conversation: {str(compact_error)}\n\n"
                                "Please use the 'Compact Session' button or start a new task."
                            )
                            raise e  # Re-raise original error

                    elif is_context_error:
                        # Already retried max times, give up
                        _save_progress_message(
                            db, task_id,
                            "❌ **Prompt is too long**\n\n"
                            "The conversation context exceeds the model's limit even after compaction.\n\n"
                            "Please use the 'Compact Session' button to manually reset, or start a new task."
                        )
                        raise
                    else:
                        # Not a context error, just propagate
                        _save_progress_message(db, task_id, f"❌ SDK query error: {str(e)}")
                        raise

            # Accumulate content from this run
            assistant_content += run_content

            # Check if we hit max iterations and task isn't complete yet
            if run_state["hit_max_iterations"] and "IMPLEMENTATION_COMPLETE" not in assistant_content:
                iteration_resume_count += 1

                if iteration_resume_count > MAX_ITERATION_RESUME_RETRIES:
                    _save_progress_message(
                        db, task_id,
                        f"⚠️ **Max iterations exhausted**\n\n"
                        f"The agent ran out of iterations after {MAX_ITERATION_RESUME_RETRIES + 1} run(s) "
                        f"({run_state['num_turns']} turns in last run). "
                        "The task may be partially complete. Please review the current state and continue manually if needed."
                    )
                    break

                _save_progress_message(
                    db, task_id,
                    f"🔄 **Auto-resuming** (continuation {iteration_resume_count}/{MAX_ITERATION_RESUME_RETRIES})\n\n"
                    f"The agent used all {run_state['num_turns']} allocated turns without completing. "
                    "Compacting context and continuing with a fresh session..."
                )

                # Compact conversation for continuation
                try:
                    compacted_summary = await _compact_conversation_context(
                        db, task_id, workspace, task, issue_details
                    )
                    _reset_session_for_compaction(db, task)

                    # Update prompt for continuation run
                    prompt_string = (
                        "You are continuing a previous implementation session that ran out of iterations. "
                        "Review what has been done so far (see the PREVIOUS SESSION SUMMARY in your system prompt) "
                        "and continue working on the remaining tasks. Focus on completing the implementation efficiently. "
                        "Remember to run validations (run_tests, run_build, run_linter) and end with IMPLEMENTATION_COMPLETE when done."
                    )
                    current_max_turns = RESUME_MAX_TURNS

                    _save_progress_message(
                        db, task_id,
                        "✅ **Context compacted** - Starting continuation run..."
                    )
                    continue  # Continue outer loop for next iteration resume

                except Exception as compact_error:
                    logger.error(f"Failed to compact for iteration resume, task {task_id}: {compact_error}")
                    _save_progress_message(
                        db, task_id,
                        f"❌ **Failed to auto-resume**\n\n"
                        f"Could not compact context for continuation: {str(compact_error)}\n\n"
                        "Please review the current state and continue manually."
                    )
                    break
            else:
                # Natural completion or IMPLEMENTATION_COMPLETE found
                break

        logger.debug(f"SDK query completed for task {task_id}, assistant_content length: {len(assistant_content)}")

        # KEEP: Completion logic (lines 1011-1067 from original)
        if not assistant_content or not assistant_content.strip():
            assistant_content = "The task has been completed successfully."

        # Check for IMPLEMENTATION_COMPLETE and run validation
        if "IMPLEMENTATION_COMPLETE" in assistant_content:
            if is_automated:

                _save_progress_message(db, task_id, "✅ WORKFLOW STATUS: Finished\n\nImplementation complete! Creating pull request...")

                try:
                    # Extract agent summary from assistant_content (remove IMPLEMENTATION_COMPLETE marker)
                    agent_summary = assistant_content.replace("IMPLEMENTATION_COMPLETE", "").strip()
                    # Limit summary length for PR comment
                    if len(agent_summary) > 2000:
                        agent_summary = agent_summary[:2000] + "\n\n...(truncated)"

                    pr_result = _create_pull_request_automatically(
                        db, workspace, task, token, issue_details, agent_summary
                    )

                    if pr_result.get("success"):
                        pr_url = pr_result.get("pr_url")
                        pr_number = pr_result.get("pr_number")

                        # Check if policy check was run
                        policy_check = pr_result.get("policy_check")
                        policy_note = ""
                        if policy_check:
                            coverage = policy_check.get("coverage_percent", 0.0)
                            warnings = policy_check.get("decision", {}).get("warnings", [])
                            if warnings:
                                policy_note = f"\n\n📊 Test Coverage: {coverage:.1f}% (⚠️ {len(warnings)} warning(s) - see PR comments)"
                            else:
                                policy_note = f"\n\n📊 Test Coverage: {coverage:.1f}% ✅"

                        _save_progress_message(
                            db,
                            task_id,
                            f"""🎉 WORKFLOW STATUS: PR Raised

    Pull request #{pr_number} has been created successfully!

    PR Details:
    - URL: {pr_url}
    - Branch: {task.agent_branch_name}
    - Status: Ready for review{policy_note}

    The automated workflow is now complete. Please review the changes and merge when ready."""
                        )

                        task.agent_status = "completed"
                        task.agent_executed_at = datetime.utcnow()
                        db.commit()
                    else:
                        # Check if it's a policy violation
                        if pr_result.get("policy_violations"):
                            violation_msg = pr_result.get("violation_message", "")
                            coverage = pr_result.get("coverage_percent", 0.0)

                            _save_progress_message(
                                db,
                                task_id,
                                f"""🛡️ WORKFLOW STATUS: Policy Check Failed

    **Test policy violations detected - PR creation blocked**

    Current Coverage: {coverage:.1f}%

    {violation_msg}

    **Next Steps:**
    1. Fix the policy violations by improving test coverage
    2. Run tests locally to verify improvements
    3. Commit your changes
    4. The PR will be created automatically once policies pass

    You can view the full policy configuration in the workspace Test Policy tab."""
                            )

                            # Mark task as needs attention (not completed)
                            task.agent_status = "idle"  # Allow retry
                            db.commit()
                        else:
                            # Regular error
                            error_msg = pr_result.get("error", "Unknown error")
                            _save_progress_message(
                                db,
                                task_id,
                                f"⚠️ Failed to create PR: {error_msg}\nPlease create the PR manually."
                            )
                except Exception as pr_error:
                    import traceback
                    traceback.print_exc()
                    _save_progress_message(
                        db,
                        task_id,
                        f"⚠️ Error creating PR: {str(pr_error)}\nPlease create the PR manually."
                    )
            

        if assistant_content:
            assistant_content = assistant_content.replace("IMPLEMENTATION_COMPLETE", "")
        # Save assistant response
        assistant_message = AgentMessage(
            workspace_task_id=task_id,
            role="assistant",
            content=assistant_content,
            user_id=None,
        )
        db.add(assistant_message)
        db.commit()

    except asyncio.CancelledError:
        # Task was cancelled by user
        _save_progress_message(db, task_id, "⏹️ Agent execution stopped by user")
        logger.info(f"Agent task {task_id} was cancelled")
        raise  # Re-raise to mark task as cancelled

    except Exception as e:
        # Log error and save detailed error message
        import traceback
        error_details = f"Error processing agent response: {str(e)}\n\nPlease try again or contact support if the issue persists."

        error_message = AgentMessage(
            workspace_task_id=task_id,
            role="system",
            content=f"❌ {error_details}",
            user_id=None,
        )
        db.add(error_message)
        db.commit()

        logger.error(f"SDK agent processing error for task {task_id}:")
        logger.error(traceback.format_exc())

    finally:
        db.close()

def _process_message(message, db, task_id: str, repo_path: str, run_state: dict = None):
    """
    Process a message from the Claude Agent SDK and yield user-friendly events.

    Captures:
    - Action status (started, completed, failed)
    - Tool usage (tool_use, tool_result)
    - Assistant responses (text blocks)
    - System messages (init, status updates)
    - Result messages (completion summary)
    """
    # Get message type from class name
    msg_type = type(message).__name__

    # Also check for subtype attribute (used by SystemMessage, ResultMessage)
    subtype = getattr(message, 'subtype', None)

    # Handle AssistantMessage - contains text and tool use
    if msg_type == 'AssistantMessage':
        content_blocks = getattr(message, 'content', [])

        for block in content_blocks:
            block_type = type(block).__name__

            if block_type == 'ToolUseBlock':
                # ACTION STARTED: Tool use initiated
                tool_name = getattr(block, 'name', '')
                tool_input = getattr(block, 'input', {})

                # Format and save tool usage start
                tool_display = _format_tool_display(tool_name, tool_input, repo_path)
                _save_progress_message(db, task_id, f"🔧 {tool_display}")

            if block_type == 'ThinkingBlock':
                # Capture thinking/reasoning (if available)
                thinking = getattr(block, 'thinking', '')
                if thinking and len(thinking.strip()) > 10:
                    _save_progress_message(db, task_id, f"🧠 Thinking: {thinking[:300]}")

    # Handle SystemMessage - initialization, status updates
    elif msg_type == 'SystemMessage':
        if subtype == 'agent_init':
            _save_progress_message(db, task_id, "🚀 Agent Initialized - Starting execution")
        elif subtype == 'turn_start':
            data = getattr(message, 'data', {})
            turn_num = data.get('turn', 0)
            if turn_num > 0 and turn_num % 5 == 0:  # Log every 5 turns
                _save_progress_message(db, task_id, f"🔄 Processing turn {turn_num}...")
        elif subtype == 'turn_end':
            # Turn completed
            pass
        elif subtype == 'status':
            # Generic status update
            data = getattr(message, 'data', {})
            status_msg = data.get('message', '')
            if status_msg:
                _save_progress_message(db, task_id, f"📊 Status: {status_msg}")

    # Handle ResultMessage - final completion summary
    elif msg_type == 'ResultMessage':
        is_error = getattr(message, 'is_error', False)
        duration_ms = getattr(message, 'duration_ms', 0)
        num_turns = getattr(message, 'num_turns', 0)
        result = getattr(message, 'result', None)
        usage = getattr(message, 'usage', None)
        session_id = getattr(message, 'session_id', None)

        # Save session_id to task for conversation continuation
        if session_id:
            task = db.query(WorkspaceTask).filter(WorkspaceTask.id == task_id).first()
            if task:
                task.claude_session_id = session_id
                db.commit()
                logger.debug(f"Saved Claude session_id {session_id} for task {task_id}")

        # Track run state for iteration/context management
        if run_state is not None:
            run_state["num_turns"] = num_turns

        # Detect max iterations exhaustion
        is_max_turns = False
        if is_error and run_state is not None:
            max_turns_limit = run_state.get("max_turns", float('inf'))
            result_lower = (result or "").lower()
            if num_turns >= max_turns_limit:
                is_max_turns = True
            elif any(kw in result_lower for kw in [
                "max turns", "max_turns", "iteration limit", "turn limit",
                "ran out of turns", "exceeded maximum"
            ]):
                is_max_turns = True

            if is_max_turns:
                run_state["hit_max_iterations"] = True

        if is_error:
            if is_max_turns:
                # Max iterations - show informational message (auto-resume will be attempted)
                _save_progress_message(
                    db, task_id,
                    f"⏳ Agent reached max iterations ({num_turns} turns, {duration_ms/1000:.1f}s)\n"
                    "Checking if auto-resume is needed..."
                )
            else:
                error_msg = f"❌ Agent Completed with Error\nTurns: {num_turns}, Duration: {duration_ms/1000:.1f}s"
                if result:
                    error_msg += f"\nError: {result}"
                _save_progress_message(db, task_id, error_msg)
        else:
            # Format completion summary
            summary_parts = [f"✅ Agent Completed Successfully"]
            summary_parts.append(f"Turns: {num_turns}, Duration: {duration_ms/1000:.1f}s")

            if usage:
                input_tokens = usage.get('input_tokens', 0)
                output_tokens = usage.get('output_tokens', 0)
                logger.info(f"Tokens: {input_tokens + output_tokens:,} ({input_tokens:,} in / {output_tokens:,} out)")

            _save_progress_message(db, task_id, "\n".join(summary_parts))

            # Save final result if available
            if result and isinstance(result, str) and len(result.strip()) > 0:
                return result
                

@router.post(
    "/{workspace_id}/tasks/{task_id}/chat/messages",
    response_model=AgentMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def send_chat_message(
    workspace_id: int,
    task_id: int,
    content: Annotated[str, Form()],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    files: Annotated[list[UploadFile] | None, File()] = None,
):
    """
    Send a message to the agent and queue response processing.

    This endpoint:
    1. Saves the user's message
    2. Queues agent processing in background
    3. Returns immediately

    The agent response will be processed asynchronously and saved to the database.
    Poll the list_chat_messages endpoint to see new messages.

    Args:
        workspace_id: Workspace ID
        task_id: Task ID
        message_data: Message content
        background_tasks: FastAPI background tasks
        db: Database session
        current_user: Current authenticated user

    Returns:
        User's message (agent response will arrive asynchronously)

    Raises:
        HTTPException: If user lacks permission or task not found
    """
    workspace, _ = get_workspace_or_403(workspace_id, db, current_user)

    # Get token and provider for workspace
    token = get_workspace_github_token_or_403(db, workspace, current_user)
    git_provider = get_git_provider_for_workspace(workspace)

    # Get task
    task = (
        db.query(WorkspaceTask)
        .filter(WorkspaceTask.id == task_id, WorkspaceTask.workspace_id == workspace_id)
        .first()
    )

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found in this workspace",
        )

    # Check if this is the first message - if so, initialize the agent
    message_count = db.query(AgentMessage).filter(
        AgentMessage.workspace_task_id == task_id
    ).count()

    is_first_message = message_count == 0

    # If first message, clone repository and create a branch for the agent to work on
    if is_first_message:
        # Check if this is a PR-linked task (has agent_pr_number) or an issue-linked task
        is_pr_task = task.agent_pr_number is not None

        # Skip initialization for PR tasks - they're initialized by _initialize_pr_task
        if is_pr_task:
            # PR tasks are already initialized, but verify and ensure repo is ready
            # Generate task-specific repository path
            repo_path = git_local_service.get_task_repo_path(workspace_id, task_id)

            # Ensure repository is cloned and PR branch is checked out with latest changes
            try:
                if not Path(repo_path).exists() or not (Path(repo_path) / ".git").exists():
                    # Clone repository if it doesn't exist
                    clone_url = git_provider.get_clone_url(workspace.github_repository, token)
                    git_local_service.ensure_repo_cloned(
                        repo_path, workspace.github_repository, token, auth_clone_url=clone_url
                    )

                # Ensure PR branch is checked out with latest changes
                if task.agent_branch_name and task.agent_pr_number:
                    # Check if branch exists locally
                    if git_local_service.branch_exists(repo_path, task.agent_branch_name):
                        # Branch exists, checkout and fetch latest PR updates
                        git_local_service.checkout_branch(repo_path, task.agent_branch_name)
                        # Fetch latest PR changes (this updates the local branch with remote PR changes)
                        git_local_service.fetch_pull_request(
                            repo_path, task.agent_pr_number, task.agent_branch_name
                        )
                    else:
                        # Fetch the PR directly using GitHub's PR refs
                        # This works for both regular PRs and PRs from forks
                        git_local_service.fetch_pull_request(
                            repo_path, task.agent_pr_number, task.agent_branch_name
                        )
                        git_local_service.checkout_branch(repo_path, task.agent_branch_name)

                    db.commit()
            except git_local_service.GitLocalError as e:
                import traceback
                traceback.print_exc()
                
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to ensure PR repository is ready: {str(e)}",
                )
        else:
            # This is an issue-linked task, initialize normally
            # Get issue details
            issue_details = git_provider.get_issue_details(
                token, workspace.github_repository, task.github_issue_number
            )

            if issue_details.get("error"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to get issue details: {issue_details['error']}",
                )

            # Generate task-specific repository path
            repo_path = git_local_service.get_task_repo_path(workspace_id, task_id)

            try:
                # Clone repository using provider-specific clone URL
                clone_url = git_provider.get_clone_url(workspace.github_repository, token)
                git_local_service.ensure_repo_cloned(
                    repo_path, workspace.github_repository, token, auth_clone_url=clone_url
                )

                # Create branch from dev branch
                issue_slug = _slugify(issue_details.get("title", ""))
                branch_name = f"coder/issue-{task.github_issue_number}-{issue_slug}"

                # Check if branch exists locally
                if not git_local_service.branch_exists(repo_path, branch_name):
                    git_local_service.create_branch(
                        repo_path, branch_name, workspace.github_dev_branch
                    )
                else:
                    # Branch exists, just checkout
                    git_local_service.checkout_branch(repo_path, branch_name)

                # Update task with branch name and local path
                task.agent_branch_name = branch_name
                task.local_repo_path = repo_path
                task.agent_status = "active"
                db.commit()

                # Add system message about initialization
                system_message = AgentMessage(
                    workspace_task_id=task_id,
                    role="system",
                    content=f"Repository cloned!\nCreated branch: {branch_name}\nAgent initialized and ready to work on the code.",
                    user_id=None,
                )
                db.add(system_message)
                db.commit()

            except git_local_service.GitLocalError as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to initialize local repository: {str(e)}",
                )

    # Ensure repository is cloned and accessible
    repo_path = task.local_repo_path
    if not repo_path:
        # Generate path if not set
        repo_path = git_local_service.get_task_repo_path(workspace_id, task_id)
        task.local_repo_path = repo_path

    # Check if repo exists, clone if needed
    if not Path(repo_path).exists() or not (Path(repo_path) / ".git").exists():
        try:
            clone_url = git_provider.get_clone_url(workspace.github_repository, token)
            git_local_service.ensure_repo_cloned(
                repo_path, workspace.github_repository, token, auth_clone_url=clone_url
            )
            # Checkout the branch if it exists
            if task.agent_branch_name:
                if git_local_service.branch_exists(repo_path, task.agent_branch_name):
                    git_local_service.checkout_branch(repo_path, task.agent_branch_name)
                else:
                    git_local_service.create_branch(
                        repo_path, task.agent_branch_name, workspace.github_dev_branch
                    )
        except git_local_service.GitLocalError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to ensure repository exists: {str(e)}",
            )

    db.commit()

    # Save user message (without attachments first, to get the ID)
    user_message = AgentMessage(
        workspace_task_id=task_id,
        role="user",
        content=content,
        user_id=current_user.id,
    )
    db.add(user_message)
    db.commit()
    db.refresh(user_message)

    # Handle file uploads if any
    attachments_list = []
    if files:
        for file in files:
            if file.filename:  # Skip empty file uploads
                file_metadata = await save_uploaded_file(workspace_id, task_id, user_message.id, file)
                attachments_list.append(file_metadata)

        # Update message with attachments
        if attachments_list:
            user_message.attachments = json.dumps(attachments_list)
            db.commit()
            db.refresh(user_message)

    # Queue agent processing via Celery
    from app.tasks.agent_tasks import process_agent_response_task
    process_agent_response_task.delay(
        workspace_id,
        task_id,
        user_message.id,
        token
    )

    # Return user message immediately (agent response will come asynchronously)
    return AgentMessageResponse(
        id=user_message.id,
        workspace_task_id=user_message.workspace_task_id,
        role=user_message.role,
        content=user_message.content,
        attachments=attachments_list if attachments_list else None,
        created_at=user_message.created_at,
        user_id=user_message.user_id,
        username=current_user.username,
    )



@router.post(
    "/{workspace_id}/tasks/{task_id}/chat/cancel",
    status_code=status.HTTP_200_OK,
)
def cancel_agent_execution(
    workspace_id: int,
    task_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Request cancellation of the current agent execution.

    This sets a flag that the background agent process will check.
    The agent will stop processing at the next safe checkpoint.

    Args:
        workspace_id: Workspace ID
        task_id: Task ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        Success message

    Raises:
        HTTPException: If user lacks permission or task not found
    """
    workspace, _ = get_workspace_or_403(workspace_id, db, current_user)

    # Get task
    task = (
        db.query(WorkspaceTask)
        .filter(WorkspaceTask.id == task_id, WorkspaceTask.workspace_id == workspace_id)
        .first()
    )

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found in this workspace",
        )

    # Set cancellation flag - we'll use agent_error field temporarily
    # In a production system, you'd add a dedicated cancel_requested field
    task.agent_status = "cancelled"
    db.commit()

    # Add system message about cancellation
    cancel_message = AgentMessage(
        workspace_task_id=task_id,
        role="system",
        content="⏹️ Agent execution cancelled by user",
        user_id=None,
    )
    db.add(cancel_message)
    db.commit()

    return {"message": "Agent execution cancellation requested"}


@router.post(
    "/{workspace_id}/tasks/{task_id}/chat/compact",
    status_code=status.HTTP_200_OK,
)
async def compact_chat_session(
    workspace_id: int,
    task_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Compact the chat session by summarizing conversation history and starting fresh.

    This is useful when the conversation context has grown too large.
    It creates a summary of the work done so far and resets the Claude session,
    allowing continued work without losing context entirely.

    Args:
        workspace_id: Workspace ID
        task_id: Task ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        Success message with summary info

    Raises:
        HTTPException: If user lacks permission or task not found
    """
    workspace, _ = get_workspace_or_403(workspace_id, db, current_user)

    # Get token and provider for workspace
    token = get_workspace_github_token_or_403(db, workspace, current_user)
    git_provider = get_git_provider_for_workspace(workspace)

    # Get task
    task = (
        db.query(WorkspaceTask)
        .filter(WorkspaceTask.id == task_id, WorkspaceTask.workspace_id == workspace_id)
        .first()
    )

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found in this workspace",
        )

    # Get issue details for context
    issue_details = git_provider.get_issue_details(
        token, workspace.github_repository, task.github_issue_number
    )

    try:
        # Generate compact summary
        summary = await _compact_conversation_context(
            db, task_id, workspace, task, issue_details
        )

        # Reset the session
        old_session_id = task.claude_session_id
        _reset_session_for_compaction(db, task)

        # Add system message about compaction
        compact_message = AgentMessage(
            workspace_task_id=task_id,
            role="system",
            content=f"📦 **Session Compacted**\n\nThe conversation context has been summarized and a fresh session started.\n\n**Summary of previous work:**\n{summary[:1500]}{'...' if len(summary) > 1500 else ''}",
            user_id=None,
        )
        db.add(compact_message)
        db.commit()

        return {
            "message": "Session compacted successfully",
            "previous_session_id": old_session_id,
            "summary_length": len(summary),
            "summary_preview": summary[:500] + "..." if len(summary) > 500 else summary
        }

    except Exception as e:
        logger.error(f"Failed to compact session for task {task_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compact session: {str(e)}",
        )


@router.delete(
    "/{workspace_id}/tasks/{task_id}/chat/messages",
    status_code=status.HTTP_204_NO_CONTENT,
)
def clear_chat_history(
    workspace_id: int,
    task_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Clear all chat messages for a task.

    Args:
        workspace_id: Workspace ID
        task_id: Task ID
        db: Database session
        current_user: Current authenticated user

    Raises:
        HTTPException: If user lacks permission or task not found
    """
    workspace, _ = get_workspace_or_403(workspace_id, db, current_user)

    # Get task
    task = (
        db.query(WorkspaceTask)
        .filter(WorkspaceTask.id == task_id, WorkspaceTask.workspace_id == workspace_id)
        .first()
    )

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found in this workspace",
        )

    # Delete all messages for this task
    db.query(AgentMessage).filter(AgentMessage.workspace_task_id == task_id).delete()
    db.commit()


@router.get(
    "/{workspace_id}/tasks/{task_id}/diff",
    status_code=status.HTTP_200_OK,
)
def get_task_diff(
    workspace_id: int,
    task_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Get the git diff for agent changes in this task.

    Returns the diff between the base branch and the agent's working branch,
    showing all changes made by the agent.

    Args:
        workspace_id: Workspace ID
        task_id: Task ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        Dict with 'files' (list of changed files) and 'diff' (full diff text)

    Raises:
        HTTPException: If user lacks permission, task not found, or diff fails
    """
    workspace, _ = get_workspace_or_403(workspace_id, db, current_user)

    # Get task
    task = (
        db.query(WorkspaceTask)
        .filter(WorkspaceTask.id == task_id, WorkspaceTask.workspace_id == workspace_id)
        .first()
    )

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found in this workspace",
        )

    if not task.local_repo_path or not task.agent_branch_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Task repository not initialized yet",
        )

    try:
        diff_data = git_local_service.get_branch_diff(
            task.local_repo_path,
            workspace.github_dev_branch,
            task.agent_branch_name
        )
        return diff_data
    except git_local_service.GitLocalError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get diff: {str(e)}",
        )


@router.get(
    "/{workspace_id}/tasks/{task_id}/file-tree",
    status_code=status.HTTP_200_OK,
)
def get_file_tree(
    workspace_id: int,
    task_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Get the repository file tree for browsing.

    Returns a nested tree structure of all files and directories in the repository,
    suitable for rendering in a file browser UI.

    Args:
        workspace_id: Workspace ID
        task_id: Task ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        Dict with:
        - 'tree': List of file/folder nodes with nested children
        - 'repo_path': Absolute path to the repository

    Raises:
        HTTPException: If user lacks permission, task not found, or repo not initialized
    """
    workspace, _ = get_workspace_or_403(workspace_id, db, current_user)

    # Get task
    task = (
        db.query(WorkspaceTask)
        .filter(WorkspaceTask.id == task_id, WorkspaceTask.workspace_id == workspace_id)
        .first()
    )

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found in this workspace",
        )

    # Check if repository is initialized
    repo_path = task.local_repo_path
    if not repo_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Repository not initialized yet. Send a message to initialize the agent.",
        )

    if not Path(repo_path).exists() or not (Path(repo_path) / ".git").exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Repository not found on disk. Send a message to re-initialize.",
        )

    try:
        tree = git_local_service.get_file_tree_recursive(repo_path, max_depth=10)
        return {
            "tree": tree,
            "repo_path": repo_path
        }
    except git_local_service.GitLocalError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get file tree: {str(e)}",
        )


@router.get(
    "/{workspace_id}/tasks/{task_id}/files",
    status_code=status.HTTP_200_OK,
)
def get_file_content(
    workspace_id: int,
    task_id: int,
    path: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Get the contents of a specific file in the repository.

    Args:
        workspace_id: Workspace ID
        task_id: Task ID
        path: Relative path to the file within the repository
        db: Database session
        current_user: Current authenticated user

    Returns:
        Dict with:
        - 'path': File path
        - 'content': File contents (or truncated for large files)
        - 'size': File size in bytes
        - 'is_binary': True if file appears to be binary
        - 'truncated': True if content was truncated due to size

    Raises:
        HTTPException: If user lacks permission, task/file not found, or read fails
    """
    workspace, _ = get_workspace_or_403(workspace_id, db, current_user)

    # Get task
    task = (
        db.query(WorkspaceTask)
        .filter(WorkspaceTask.id == task_id, WorkspaceTask.workspace_id == workspace_id)
        .first()
    )

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found in this workspace",
        )

    # Check if repository is initialized
    repo_path = task.local_repo_path
    if not repo_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Repository not initialized yet",
        )

    # Security: Prevent path traversal attacks
    if ".." in path or path.startswith("/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file path",
        )

    # Construct full file path
    full_path = Path(repo_path) / path

    # Verify file exists and is within repo
    if not full_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {path}",
        )

    if not full_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Path is not a file: {path}",
        )

    # Verify file is within repository (prevent traversal)
    try:
        full_path.relative_to(repo_path)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    try:
        # Get file size
        file_size = full_path.stat().st_size

        # Check if file is binary by trying to read as text
        is_binary = False
        content = ""
        truncated = False
        max_size = 500 * 1024  # 500KB limit for text files

        try:
            # Try reading as text
            with open(full_path, 'r', encoding='utf-8') as f:
                if file_size > max_size:
                    # Read only first 500KB
                    content = f.read(max_size)
                    truncated = True
                else:
                    content = f.read()
        except (UnicodeDecodeError, UnicodeError):
            # File is binary
            is_binary = True
            content = ""

        return {
            "path": path,
            "content": content,
            "size": file_size,
            "is_binary": is_binary,
            "truncated": truncated
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read file: {str(e)}",
        )


def _get_attachments_context(task: WorkspaceTask) -> str:
    """
    Get formatted attachment context for agent prompt.

    Args:
        task: WorkspaceTask with potential attachments_metadata

    Returns:
        Formatted string with attachment context, or empty string if no attachments
    """
    if not task.attachments_metadata:
        return ""

    try:
        from app.services.document_processor_service import document_processor

        # Parse attachments metadata
        attachments_data = json.loads(task.attachments_metadata)

        # Check if there are successfully processed attachments
        if attachments_data.get("successfully_processed", 0) == 0:
            return ""

        # Get formatted context from document processor
        attachment_context = document_processor.compile_agent_context(
            attachments_data.get("attachments", [])
        )

        return attachment_context

    except Exception as e:
        logger.warning(f"Failed to load attachment context for task {task.id}: {e}")
        return ""
