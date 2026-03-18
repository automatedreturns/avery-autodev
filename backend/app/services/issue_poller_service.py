"""Service for polling git provider issues and auto-linking them to workspaces."""

import json
import logging
import threading
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.models.workspace import Workspace
from app.models.workspace_task import WorkspaceTask
from app.models.polling_status import PollingStatus
from app.services.encryption_service import decrypt_token
from app.services.git_providers import get_git_provider_for_workspace

logger = logging.getLogger(__name__)


def _trigger_conflict_resolution_for_pr(workspace_id: int, task_id: int, pr_number: int, token: str) -> None:
    """
    Trigger automatic conflict resolution for a PR with merge conflicts.

    This function runs in a background thread and:
    1. Initializes the agent (clones repo, checks out PR branch)
    2. Sends an automatic message to resolve conflicts
    3. Queues agent processing via Celery
    """
    from app.database import SessionLocal
    from pathlib import Path
    from app.services import git_local_service
    from app.tasks.agent_tasks import process_agent_response_task

    db = SessionLocal()

    try:
        # Get workspace and task
        workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
        task = db.query(WorkspaceTask).filter(WorkspaceTask.id == task_id).first()

        if not workspace or not task:
            logger.error(f"Workspace {workspace_id} or task {task_id} not found for PR conflict resolution")
            return

        # Get PR details via provider
        git_provider = get_git_provider_for_workspace(workspace)
        pr_details = git_provider.get_pull_request_details(
            token, workspace.github_repository, pr_number
        )

        if pr_details.get("error"):
            logger.error(f"Failed to get PR details for conflict resolution: {pr_details['error']}")
            return

        # Generate task-specific repository path
        repo_path = git_local_service.get_task_repo_path(workspace_id, task_id)

        try:
            # Clone repository using provider-specific clone URL
            clone_url = git_provider.get_clone_url(workspace.github_repository, token)
            git_local_service.ensure_repo_cloned(
                repo_path, workspace.github_repository, token, auth_clone_url=clone_url
            )

            # Configure git user for commits
            git_local_service.configure_git_user(repo_path)

            # Fetch latest changes
            git_local_service.fetch(repo_path)

            # Checkout PR branch
            pr_branch = pr_details.get("head_branch")
            if not pr_branch:
                logger.error(f"No head branch found for PR #{pr_number}")
                return

            # Check if branch exists locally
            if not git_local_service.branch_exists(repo_path, pr_branch):
                # Create local branch tracking remote
                git_local_service.checkout_remote_branch(repo_path, pr_branch)
            else:
                # Branch exists, just checkout
                git_local_service.checkout_branch(repo_path, pr_branch)

            # Update task with branch name and local path
            task.agent_branch_name = pr_branch
            task.local_repo_path = repo_path
            task.agent_status = "active"
            db.commit()

            logger.info(f"Repository initialized for PR conflict resolution: {repo_path}")

            # Add system message about initialization
            from app.models.agent_message import AgentMessage

            system_message = AgentMessage(
                workspace_task_id=task_id,
                role="system",
                content=f"""WORKFLOW STATUS: Merge Conflict Detected

PR #{pr_number} has merge conflicts with the base branch '{pr_details.get('base_branch')}'.

Repository Setup:
- Checked out branch: {pr_branch}
- Agent initialized and ready to resolve conflicts

Next Step: Agent will automatically resolve merge conflicts.""",
                user_id=None,
            )
            db.add(system_message)
            db.commit()

        except Exception as e:
            logger.error(f"Failed to initialize git repo for PR conflict resolution: {str(e)}")

            # Add error message to chat
            from app.models.agent_message import AgentMessage

            error_message = AgentMessage(
                workspace_task_id=task_id,
                role="system",
                content=f"Error initializing repository: {str(e)}",
                user_id=None,
            )
            db.add(error_message)
            db.commit()
            return

        # Create automatic conflict resolution message
        from app.models.agent_message import AgentMessage

        base_branch = pr_details.get("base_branch", "main")
        automatic_message_content = f"""This PR (#{pr_number}) has merge conflicts with the base branch '{base_branch}'.

**PR #{pr_number}: {pr_details.get('title')}**

{pr_details.get('body', 'No description provided.')}

**IMPORTANT INSTRUCTIONS:**
This is an automated conflict resolution workflow. Please:
1. Merge the latest changes from '{base_branch}' into this branch
2. Resolve any conflicts that arise
3. Test to ensure the code still works correctly
4. Commit and push the resolved changes
5. When you're fully satisfied with the resolution, respond with the exact phrase: "CONFLICTS_RESOLVED"

You have full autonomy to resolve conflicts. Do NOT ask for permission before each file modification. Just resolve the conflicts and commit your changes."""

        # Create message in database
        message = AgentMessage(
            workspace_task_id=task_id,
            role="user",
            content=automatic_message_content,
            user_id=workspace.owner_id,
        )
        db.add(message)
        db.commit()
        db.refresh(message)

        logger.info(f"Created automatic conflict resolution message for PR #{pr_number}, task {task_id}")

        # Queue agent processing via Celery
        process_agent_response_task.delay(
            workspace_id=workspace_id,
            task_id=task_id,
            user_message_id=message.id,
            token=token,
        )

        logger.info(f"Queued agent processing for PR conflict resolution task {task_id} in workspace {workspace_id}")

    except Exception as e:
        logger.error(f"Error in PR conflict resolution for task {task_id}: {str(e)}")
    finally:
        db.close()


def _trigger_initial_analysis_for_polled_task(workspace_id: int, task_id: int, token: str) -> None:
    """
    Trigger automatic issue analysis for a task created by polling.

    This function runs in a background thread and:
    1. Initializes the agent (clones repo, creates branch)
    2. Sends an automatic message to analyze the issue
    3. Queues agent processing via Celery
    """
    from app.database import SessionLocal
    from pathlib import Path
    from app.services import git_local_service
    from app.services.coder_agent_service import _slugify
    from app.tasks.agent_tasks import process_agent_response_task

    db = SessionLocal()

    try:
        # Get workspace and task
        workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
        task = db.query(WorkspaceTask).filter(WorkspaceTask.id == task_id).first()

        if not workspace or not task:
            logger.error(f"Workspace {workspace_id} or task {task_id} not found for auto-analysis")
            return

        # Get issue details via provider
        git_provider = get_git_provider_for_workspace(workspace)
        issue_details = git_provider.get_issue_details(
            token, workspace.github_repository, task.github_issue_number
        )

        if issue_details.get("error"):
            logger.error(f"Failed to get issue details for auto-analysis: {issue_details['error']}")
            return

        # Generate task-specific repository path
        repo_path = git_local_service.get_task_repo_path(workspace_id, task_id)

        try:
            # Clone repository using provider-specific clone URL
            clone_url = git_provider.get_clone_url(workspace.github_repository, token)
            git_local_service.ensure_repo_cloned(
                repo_path, workspace.github_repository, token, auth_clone_url=clone_url
            )

            # Configure git user for commits
            git_local_service.configure_git_user(repo_path)

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

            logger.info(f"Repository initialized for auto-analysis: {repo_path}")

            # Add system message about initialization with workflow status
            from app.models.agent_message import AgentMessage

            system_message = AgentMessage(
                workspace_task_id=task_id,
                role="system",
                content=f"""WORKFLOW STATUS: Issue Picked

Issue #{task.github_issue_number} has been automatically imported from GitHub polling.

Repository Setup:
- Created branch: {branch_name}
- Agent initialized and ready to implement code changes

Next Step: Agent will start working on the implementation automatically.""",
                user_id=None,
            )
            db.add(system_message)
            db.commit()

        except Exception as e:
            logger.error(f"Failed to initialize git repo for auto-analysis: {str(e)}")

            # Add error message to chat
            from app.models.agent_message import AgentMessage

            error_message = AgentMessage(
                workspace_task_id=task_id,
                role="system",
                content=f"Error initializing repository: {str(e)}",
                user_id=None,
            )
            db.add(error_message)
            db.commit()
            return

        # Note: Attachment processing is handled by the agent when it starts
        # This ensures processing happens synchronously before agent uses the context

        # Create automatic analysis message
        from app.models.agent_message import AgentMessage

        issue_body = issue_details.get("body", "No description provided.")
        automatic_message_content = f"""This issue has been automatically imported from GitHub with the 'avery-developer' label. I need you to implement the required code changes automatically.

**Issue #{task.github_issue_number}: {issue_details.get('title')}**

{issue_body}

**IMPORTANT INSTRUCTIONS:**
This is an automated workflow. Please:
1. Analyze the issue and understand what needs to be done
2. Read the relevant files to understand the codebase
3. Implement the required code changes WITHOUT asking for approval
4. Make commits as you complete each logical piece of work
5. When you're fully satisfied with your implementation, respond with the exact phrase: "IMPLEMENTATION_COMPLETE"

You have full autonomy to make code changes. Do NOT ask for permission before each file modification. Just implement the solution and commit your changes."""

        # Create message in database
        message = AgentMessage(
            workspace_task_id=task_id,
            role="user",
            content=automatic_message_content,
            user_id=workspace.owner_id,
        )
        db.add(message)
        db.commit()
        db.refresh(message)

        logger.info(f"Created automatic analysis message for task {task_id}")

        # Queue agent processing via Celery
        process_agent_response_task.delay(
            workspace_id=workspace_id,
            task_id=task_id,
            user_message_id=message.id,
            token=token,
        )

        logger.info(f"Queued agent processing for task {task_id} in workspace {workspace_id}")

    except Exception as e:
        logger.error(f"Error in auto-analysis for task {task_id}: {str(e)}")
    finally:
        db.close()


def poll_workspace_issues(
    db: Session,
    workspace: Workspace,
    github_token: str,
    label_filter: str = "avery-developer",
    triggered_by: str = "automatic"
) -> dict:
    """
    Poll GitHub for new issues with specific label and auto-link them to workspace.

    Args:
        db: Database session
        workspace: Workspace to poll for
        github_token: GitHub access token
        label_filter: Label to filter issues by (default: "avery-developer")

    Returns:
        dict with polling results: {
            "success": bool,
            "issues_found": int,
            "issues_linked": int,
            "issues_skipped": int,
            "error": str | None
        }
    """
    try:
        # Get provider for this workspace
        git_provider = get_git_provider_for_workspace(workspace)

        # Get all open issues from the repository (skip cache to get latest data)
        issues_result = git_provider.list_issues(
            github_token,
            workspace.github_repository,
            state="open",
            per_page=100,
            page=1,
            skip_cache=True  # Always fetch fresh data during polling
        )

        if issues_result.get("error"):
            return {
                "success": False,
                "issues_found": 0,
                "issues_linked": 0,
                "issues_skipped": 0,
                "error": f"Failed to fetch issues: {issues_result['error']}"
            }

        issues = issues_result.get("issues", [])

        logger.info(f"Workspace {workspace.id}: Found {len(issues)} total issues")

        # Filter issues by label
        labeled_issues = [
            issue for issue in issues
            if label_filter in [label.lower() for label in issue.get("labels", [])]
        ]

        logger.info(f"Workspace {workspace.id}: Filtered to {len(labeled_issues)} issues with label '{label_filter}'")

        issues_found = len(labeled_issues)
        issues_linked = 0
        issues_skipped = 0
        issues_deferred = 0
        linked_issue_numbers = []
        deferred_issue_numbers = []

        # Get already linked issue numbers
        existing_tasks = db.query(WorkspaceTask.github_issue_number).filter(
            WorkspaceTask.workspace_id == workspace.id
        ).all()
        existing_issue_numbers = {task.github_issue_number for task in existing_tasks}

        # Auto-link new issues
        for issue in labeled_issues:
            issue_number = issue.get("number")
            logger.debug(f"Processing issue #{issue_number}: {issue.get('title')} with labels {issue.get('labels')}")

            # Skip if already linked
            if issue_number in existing_issue_numbers:
                issues_skipped += 1
                logger.info(f"Issue #{issue_number} already linked to workspace {workspace.id}")
                continue

            # Check "blocked by" relationships before importing
            blocked_result = git_provider.get_issue_blocked_by(
                github_token, workspace.github_repository, issue_number
            )

            if blocked_result.get("error"):
                logger.warning(
                    f"Issue #{issue_number}: blocked-by check failed: {blocked_result['error']}. "
                    f"Importing anyway (fail-open)."
                )
            elif blocked_result.get("is_blocked"):
                blocker_refs = [
                    f"{b['repo']}#{b['number']}" for b in blocked_result["open_blockers"]
                ]
                logger.info(
                    f"Issue #{issue_number} is blocked by {len(blocked_result['open_blockers'])} "
                    f"open issue(s): {', '.join(blocker_refs)}. Deferring import."
                )
                issues_deferred += 1
                deferred_issue_numbers.append(issue_number)
                continue

            # Create new task link
            try:
                new_task = WorkspaceTask(
                    workspace_id=workspace.id,
                    github_issue_number=issue_number,
                    github_issue_title=issue.get("title"),
                    added_by_user_id=workspace.owner_id,  # Use workspace owner as creator
                )
                db.add(new_task)
                db.commit()
                db.refresh(new_task)

                issues_linked += 1
                linked_issue_numbers.append(issue_number)
                logger.info(f"Auto-linked issue #{issue_number} to workspace {workspace.id}")

                # Trigger automatic analysis in background thread
                # We still use a thread here to avoid blocking the polling loop,
                # but the thread will quickly queue the work to Celery and return
                thread = threading.Thread(
                    target=_trigger_initial_analysis_for_polled_task,
                    args=(workspace.id, new_task.id, github_token)
                )
                thread.daemon = True
                thread.start()
                logger.info(f"Queued automatic analysis for issue #{issue_number} in workspace {workspace.id}")

            except Exception as e:
                logger.error(f"Failed to link issue #{issue_number}: {str(e)}")
                db.rollback()
                continue

        # Update workspace last polled time
        workspace.last_issue_poll = datetime.utcnow()
        db.commit()

        # Update or create polling status
        status = db.query(PollingStatus).filter(
            PollingStatus.workspace_id == workspace.id
        ).first()

        if status:
            # Update existing status
            status.last_poll_time = datetime.utcnow()
            status.total_issues_imported += issues_linked
            status.last_poll_issues_found = issues_found
            status.last_poll_issues_linked = issues_linked
            status.last_poll_issues_skipped = issues_skipped
            status.last_poll_issues_deferred = issues_deferred
            status.last_poll_deferred_issue_numbers = json.dumps(deferred_issue_numbers) if deferred_issue_numbers else None
            status.last_poll_status = "success"
            status.last_poll_error = None
            status.updated_at = datetime.utcnow()
        else:
            # Create new status
            status = PollingStatus(
                workspace_id=workspace.id,
                last_poll_time=datetime.utcnow(),
                total_issues_imported=issues_linked,
                last_poll_issues_found=issues_found,
                last_poll_issues_linked=issues_linked,
                last_poll_issues_skipped=issues_skipped,
                last_poll_issues_deferred=issues_deferred,
                last_poll_deferred_issue_numbers=json.dumps(deferred_issue_numbers) if deferred_issue_numbers else None,
                last_poll_status="success",
                last_poll_error=None,
            )
            db.add(status)

        db.commit()

        return {
            "success": True,
            "issues_found": issues_found,
            "issues_linked": issues_linked,
            "issues_skipped": issues_skipped,
            "issues_deferred": issues_deferred,
            "deferred_issue_numbers_json": json.dumps(deferred_issue_numbers) if deferred_issue_numbers else None,
            "error": None
        }

    except Exception as e:
        logger.error(f"Error polling issues for workspace {workspace.id}: {str(e)}")

        # Save error to status
        try:
            status = db.query(PollingStatus).filter(
                PollingStatus.workspace_id == workspace.id
            ).first()

            if status:
                # Update existing status
                status.last_poll_time = datetime.utcnow()
                status.last_poll_issues_found = 0
                status.last_poll_issues_linked = 0
                status.last_poll_issues_skipped = 0
                status.last_poll_issues_deferred = 0
                status.last_poll_deferred_issue_numbers = None
                status.last_poll_status = "error"
                status.last_poll_error = str(e)
                status.updated_at = datetime.utcnow()
            else:
                # Create new status with error
                status = PollingStatus(
                    workspace_id=workspace.id,
                    last_poll_time=datetime.utcnow(),
                    total_issues_imported=0,
                    last_poll_issues_found=0,
                    last_poll_issues_linked=0,
                    last_poll_issues_skipped=0,
                    last_poll_issues_deferred=0,
                    last_poll_deferred_issue_numbers=None,
                    last_poll_status="error",
                    last_poll_error=str(e),
                )
                db.add(status)

            db.commit()
        except Exception as status_error:
            logger.error(f"Failed to save error status: {str(status_error)}")

        return {
            "success": False,
            "issues_found": 0,
            "issues_linked": 0,
            "issues_skipped": 0,
            "issues_deferred": 0,
            "deferred_issue_numbers_json": None,
            "error": str(e)
        }


def poll_workspace_prs(
    db: Session,
    workspace: Workspace,
    github_token: str,
    label_filter: str = "avery-developer",
    triggered_by: str = "automatic"
) -> dict:
    """
    Poll GitHub for PRs with merge conflicts tagged with specific label.

    Args:
        db: Database session
        workspace: Workspace to poll for
        github_token: GitHub access token
        label_filter: Label to filter PRs by (default: "avery-developer")

    Returns:
        dict with polling results: {
            "success": bool,
            "prs_checked": int,
            "prs_with_conflicts": int,
            "pr_tasks_created": int,
            "error": str | None
        }
    """
    try:
        # Get provider for this workspace
        git_provider = get_git_provider_for_workspace(workspace)

        # Get all open PRs/MRs from the repository (skip cache to get latest data)
        prs_result = git_provider.list_pull_requests(
            github_token,
            workspace.github_repository,
            state="open",
            per_page=100,
            page=1,
            skip_cache=True  # Always fetch fresh data during polling
        )

        if prs_result.get("error"):
            return {
                "success": False,
                "prs_checked": 0,
                "prs_with_conflicts": 0,
                "pr_tasks_created": 0,
                "error": f"Failed to fetch PRs: {prs_result['error']}"
            }

        prs = prs_result.get("pull_requests", [])

        logger.info(f"Workspace {workspace.id}: Found {len(prs)} total PRs")

        # Filter PRs by label
        labeled_prs = [
            pr for pr in prs
            if label_filter in [label.lower() for label in pr.get("labels", [])]
        ]

        logger.info(f"Workspace {workspace.id}: Filtered to {len(labeled_prs)} PRs with label '{label_filter}'")

        prs_checked = len(labeled_prs)
        prs_with_conflicts = 0
        pr_tasks_created = 0

        # Check each PR for conflicts
        for pr in labeled_prs:
            pr_number = pr.get("number")
            logger.debug(f"Processing PR #{pr_number}: {pr.get('title')} with labels {pr.get('labels')}")

            # Get detailed PR info to check for conflicts
            pr_details = git_provider.get_pull_request_details(
                github_token, workspace.github_repository, pr_number
            )

            if pr_details.get("error"):
                logger.error(f"Failed to get details for PR #{pr_number}: {pr_details['error']}")
                continue

            # Check if PR has conflicts
            has_conflicts = pr_details.get("has_conflicts", False)

            if not has_conflicts:
                logger.debug(f"PR #{pr_number} has no conflicts, skipping")
                continue

            prs_with_conflicts += 1
            logger.info(f"PR #{pr_number} has merge conflicts")

            # Check if task already exists for this PR
            existing_task = db.query(WorkspaceTask).filter(
                WorkspaceTask.workspace_id == workspace.id,
                WorkspaceTask.agent_pr_number == pr_number
            ).first()

            if existing_task:
                if existing_task.agent_status == "running":
                    logger.info(f"Task already exists for PR #{pr_number} and is currently running, skipping")
                    continue

                # Task exists but not running - check if enough time has passed to re-trigger
                if existing_task.agent_executed_at:
                    time_since_last_execution = datetime.utcnow() - existing_task.agent_executed_at
                    if time_since_last_execution < timedelta(minutes=30):
                        logger.info(f"Task for PR #{pr_number} was executed recently ({time_since_last_execution.total_seconds()/60:.1f} minutes ago), skipping")
                        continue

                # Re-trigger conflict resolution for existing task
                logger.info(f"Re-triggering conflict resolution for PR #{pr_number} (status: {existing_task.agent_status})")
                thread = threading.Thread(
                    target=_trigger_conflict_resolution_for_pr,
                    args=(workspace.id, existing_task.id, pr_number, github_token)
                )
                thread.daemon = True
                thread.start()
                logger.info(f"Queued automatic conflict resolution for PR #{pr_number} in workspace {workspace.id}")
                continue

            # Create new task for conflict resolution
            try:
                new_task = WorkspaceTask(
                    workspace_id=workspace.id,
                    github_issue_number=pr_number,  # Store PR number as issue number for compatibility
                    github_issue_title=f"Resolve merge conflicts for PR #{pr_number}: {pr.get('title')}",
                    added_by_user_id=workspace.owner_id,
                    agent_pr_number=pr_number,
                    agent_pr_url=pr_details.get("html_url"),
                )
                db.add(new_task)
                db.commit()
                db.refresh(new_task)

                pr_tasks_created += 1
                logger.info(f"Created conflict resolution task for PR #{pr_number} in workspace {workspace.id}")

                # Trigger automatic conflict resolution in background thread
                thread = threading.Thread(
                    target=_trigger_conflict_resolution_for_pr,
                    args=(workspace.id, new_task.id, pr_number, github_token)
                )
                thread.daemon = True
                thread.start()
                logger.info(f"Queued automatic conflict resolution for PR #{pr_number} in workspace {workspace.id}")

            except Exception as e:
                logger.error(f"Failed to create task for PR #{pr_number}: {str(e)}")
                db.rollback()
                continue

        return {
            "success": True,
            "prs_checked": prs_checked,
            "prs_with_conflicts": prs_with_conflicts,
            "pr_tasks_created": pr_tasks_created,
            "error": None
        }

    except Exception as e:
        logger.error(f"Error polling PRs for workspace {workspace.id}: {str(e)}")
        return {
            "success": False,
            "prs_checked": 0,
            "prs_with_conflicts": 0,
            "pr_tasks_created": 0,
            "error": str(e)
        }


def poll_workspace_issues_and_prs(
    db: Session,
    workspace: Workspace,
    github_token: str,
    label_filter: str = "avery-developer",
    triggered_by: str = "automatic"
) -> dict:
    """
    Poll GitHub for both new issues and PRs with merge conflicts, both tagged with specific label.

    Args:
        db: Database session
        workspace: Workspace to poll for
        github_token: GitHub access token
        label_filter: Label to filter by (default: "avery-developer")

    Returns:
        dict with combined polling results
    """
    try:
        # Poll for issues
        issues_result = poll_workspace_issues(
            db, workspace, github_token, label_filter, triggered_by
        )

        # Poll for PRs with conflicts
        prs_result = poll_workspace_prs(
            db, workspace, github_token, label_filter, triggered_by
        )

        # Combine results
        combined_success = issues_result["success"] and prs_result["success"]
        combined_error = None

        if not combined_success:
            errors = []
            if issues_result.get("error"):
                errors.append(f"Issues: {issues_result['error']}")
            if prs_result.get("error"):
                errors.append(f"PRs: {prs_result['error']}")
            combined_error = "; ".join(errors) if errors else None

        # Update polling status with combined results
        status = db.query(PollingStatus).filter(
            PollingStatus.workspace_id == workspace.id
        ).first()

        if status:
            # Update existing status
            status.last_poll_time = datetime.utcnow()
            status.last_poll_issues_found = issues_result.get("issues_found", 0)
            status.last_poll_issues_linked = issues_result.get("issues_linked", 0)
            status.last_poll_issues_skipped = issues_result.get("issues_skipped", 0)
            status.last_poll_issues_deferred = issues_result.get("issues_deferred", 0)
            status.last_poll_deferred_issue_numbers = issues_result.get("deferred_issue_numbers_json")
            status.last_poll_prs_checked = prs_result.get("prs_checked", 0)
            status.last_poll_prs_with_conflicts = prs_result.get("prs_with_conflicts", 0)
            status.total_pr_tasks_created += prs_result.get("pr_tasks_created", 0)
            status.last_poll_status = "success" if combined_success else "error"
            status.last_poll_error = combined_error
            status.updated_at = datetime.utcnow()
        else:
            # Create new status
            status = PollingStatus(
                workspace_id=workspace.id,
                last_poll_time=datetime.utcnow(),
                total_issues_imported=issues_result.get("issues_linked", 0),
                last_poll_issues_found=issues_result.get("issues_found", 0),
                last_poll_issues_linked=issues_result.get("issues_linked", 0),
                last_poll_issues_skipped=issues_result.get("issues_skipped", 0),
                last_poll_issues_deferred=issues_result.get("issues_deferred", 0),
                last_poll_deferred_issue_numbers=issues_result.get("deferred_issue_numbers_json"),
                last_poll_prs_checked=prs_result.get("prs_checked", 0),
                last_poll_prs_with_conflicts=prs_result.get("prs_with_conflicts", 0),
                total_pr_tasks_created=prs_result.get("pr_tasks_created", 0),
                last_poll_status="success" if combined_success else "error",
                last_poll_error=combined_error,
            )
            db.add(status)

        db.commit()

        return {
            "success": combined_success,
            "issues_found": issues_result.get("issues_found", 0),
            "issues_linked": issues_result.get("issues_linked", 0),
            "issues_skipped": issues_result.get("issues_skipped", 0),
            "issues_deferred": issues_result.get("issues_deferred", 0),
            "prs_checked": prs_result.get("prs_checked", 0),
            "prs_with_conflicts": prs_result.get("prs_with_conflicts", 0),
            "pr_tasks_created": prs_result.get("pr_tasks_created", 0),
            "error": combined_error
        }

    except Exception as e:
        logger.error(f"Error polling issues and PRs for workspace {workspace.id}: {str(e)}")
        return {
            "success": False,
            "issues_found": 0,
            "issues_linked": 0,
            "issues_skipped": 0,
            "issues_deferred": 0,
            "prs_checked": 0,
            "prs_with_conflicts": 0,
            "pr_tasks_created": 0,
            "error": str(e)
        }


def poll_all_workspaces(db: Session) -> dict:
    """
    Poll all workspaces for new issues and PRs with the 'avery-developer' label.

    Args:
        db: Database session

    Returns:
        dict with results: {
            "success": bool,
            "workspaces_polled": int,
            "total_issues_linked": int,
            "total_pr_tasks_created": int,
            "errors": list[str]
        }
    """
    try:
        # Get all workspaces
        workspaces = db.query(Workspace).all()

        workspaces_polled = 0
        total_issues_linked = 0
        total_issues_deferred = 0
        total_pr_tasks_created = 0
        errors = []

        for workspace in workspaces:
            # Skip if polling is disabled for this workspace
            if not workspace.polling_enabled:
                logger.debug(f"Skipping workspace {workspace.id}: Polling disabled")
                continue

            # Skip if no owner or owner has no token for the workspace's provider
            if not workspace.owner:
                logger.warning(f"Skipping workspace {workspace.id}: No owner")
                continue

            provider = getattr(workspace, "git_provider", None) or "github"
            if provider == "gitlab":
                if not workspace.owner.gitlab_token_encrypted:
                    logger.warning(f"Skipping workspace {workspace.id}: No GitLab token")
                    continue
            else:
                if not workspace.owner.github_token_encrypted:
                    logger.warning(f"Skipping workspace {workspace.id}: No GitHub token")
                    continue

            try:
                # Decrypt owner's token for the appropriate provider
                token_field = "gitlab_token_encrypted" if provider == "gitlab" else "github_token_encrypted"
                github_token = decrypt_token(getattr(workspace.owner, token_field))

                # Poll this workspace for both issues and PRs
                result = poll_workspace_issues_and_prs(db, workspace, github_token)

                if result["success"]:
                    workspaces_polled += 1
                    total_issues_linked += result["issues_linked"]
                    total_issues_deferred += result.get("issues_deferred", 0)
                    total_pr_tasks_created += result["pr_tasks_created"]

                    if result["issues_linked"] > 0 or result["pr_tasks_created"] > 0 or result.get("issues_deferred", 0) > 0:
                        logger.info(
                            f"Workspace {workspace.id}: Linked {result['issues_linked']} new issues, "
                            f"deferred {result.get('issues_deferred', 0)} blocked issues, "
                            f"created {result['pr_tasks_created']} PR conflict tasks"
                        )
                else:
                    errors.append(f"Workspace {workspace.id}: {result['error']}")

            except Exception as e:
                error_msg = f"Workspace {workspace.id}: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)
                continue

        return {
            "success": True,
            "workspaces_polled": workspaces_polled,
            "total_issues_linked": total_issues_linked,
            "total_issues_deferred": total_issues_deferred,
            "total_pr_tasks_created": total_pr_tasks_created,
            "errors": errors
        }

    except Exception as e:
        logger.error(f"Error polling all workspaces: {str(e)}")
        return {
            "success": False,
            "workspaces_polled": 0,
            "total_issues_linked": 0,
            "total_issues_deferred": 0,
            "total_pr_tasks_created": 0,
            "errors": [str(e)]
        }
