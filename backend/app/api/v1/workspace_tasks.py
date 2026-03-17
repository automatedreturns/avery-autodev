"""Workspace task management API endpoints."""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.permissions import get_workspace_or_403
from app.database import get_db
from app.models.subscription import EventType
from app.models.user import User
from app.models.workspace_task import WorkspaceTask
from app.services.subscription_service import SubscriptionService
from app.schemas.workspace_task import (
    AvailableIssuesResponse,
    FeatureRequestCreate,
    FeatureRequestResponse,
    GitHubIssuePreview,
    SimilarIssuesResponse,
    SimilarIssuesSearch,
    WorkspaceTaskCreate,
    WorkspaceTaskListResponse,
    WorkspaceTaskResponse,
)
from app.services.workspace_token_service import get_workspace_github_token_or_403
from app.services.git_providers import get_git_provider_for_workspace
from app.models.agent_message import AgentMessage

router = APIRouter()


def _trigger_initial_analysis(workspace_id: int, task_id: int, token: str, pr_number: int | None = None) -> None:
    """
    Trigger automatic analysis when a task is first linked.

    For issues: Initializes agent, creates branch, and analyzes the issue
    For PRs: Checks out PR branch, analyzes for conflicts, and provides PR context

    This function runs in the background after a task is created and:
    1. Initializes the agent (clones repo, checks out appropriate branch)
    2. Sends an automatic message to analyze the issue/PR
    3. Queues agent processing via Celery

    Args:
        workspace_id: Workspace ID
        task_id: Task ID
        token: GitHub token
        pr_number: PR number if analyzing a PR, None for issues
    """
    from app.database import SessionLocal
    from pathlib import Path
    from app.services import git_local_service
    from app.services.git_providers import get_git_provider_for_workspace as _get_provider
    from app.services.coder_agent_service import _slugify
    from app.tasks.agent_tasks import process_agent_response_task

    db = SessionLocal()

    try:
        # Get workspace and task
        from app.models.workspace import Workspace
        workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
        task = db.query(WorkspaceTask).filter(WorkspaceTask.id == task_id).first()

        if not workspace or not task:
            return

        git_provider = _get_provider(workspace)

        # Generate task-specific repository path
        repo_path = git_local_service.get_task_repo_path(workspace_id, task_id)

        try:
            # Clone repository using provider-specific clone URL
            clone_url = git_provider.get_clone_url(workspace.github_repository, token)
            git_local_service.ensure_repo_cloned(
                repo_path, workspace.github_repository, token, auth_clone_url=clone_url
            )

            if pr_number:
                # PR Analysis Path
                pr_details = git_provider.get_pull_request_details(
                    token, workspace.github_repository, pr_number
                )

                if pr_details.get("error"):
                    error_message = AgentMessage(
                        workspace_task_id=task_id,
                        role="system",
                        content=f"Error fetching PR details: {pr_details['error']}",
                        user_id=None,
                    )
                    db.add(error_message)
                    db.commit()
                    return

                # Checkout the PR's branch
                branch_name = pr_details["head_branch"]

                # Check if branch exists locally
                if not git_local_service.branch_exists(repo_path, branch_name):
                    # Fetch the PR directly using GitHub's PR refs
                    git_local_service.fetch_pull_request(repo_path, pr_number, branch_name)

                # Checkout the branch
                git_local_service.checkout_branch(repo_path, branch_name)

                # Update task with local repo path and branch
                task.local_repo_path = repo_path
                task.agent_branch_name = branch_name
                task.agent_status = "active"
                db.commit()

                # Build initialization message with branch info
                init_parts = [
                    f"Repository cloned!",
                    f"Checked out PR branch: **{branch_name}**",
                    f"Base branch: **{pr_details['base_branch']}**"
                ]

                # Check for merge conflicts
                has_conflicts = pr_details.get("has_conflicts", False)
                mergeable_state = pr_details.get("mergeable_state", "unknown")

                if has_conflicts:
                    init_parts.append(f"\n⚠️ **This PR has merge conflicts that need to be resolved before merging into {pr_details['base_branch']}**")
                    init_parts.append(f"Mergeable state: {mergeable_state}")
                else:
                    init_parts.append(f"\n✅ No merge conflicts detected. PR can be merged into {pr_details['base_branch']}.")

                # Create system message with initialization details
                system_message = AgentMessage(
                    workspace_task_id=task_id,
                    role="system",
                    content="\n".join(init_parts),
                    user_id=None,
                )
                db.add(system_message)
                db.commit()

                # Create automatic analysis request message for PR
                if has_conflicts:
                    auto_message_content = f"""Please analyze this Pull Request and its merge conflicts.

**PR #{pr_number}: {pr_details.get('title', 'N/A')}**

**Branches:**
- Source branch: `{branch_name}`
- Target branch: `{pr_details['base_branch']}`

**Status:** This PR has merge conflicts with the base branch `{pr_details['base_branch']}`.

Please provide:
1. An analysis of the changes in this PR
2. Identification of which files have conflicts (you may need to attempt a merge to see specific conflicts)
3. Your recommended approach to resolve the conflicts
4. Any potential issues or considerations when merging

Feel free to explore the codebase and attempt a test merge to identify specific conflict areas."""
                else:
                    auto_message_content = f"""Please analyze this Pull Request.

**PR #{pr_number}: {pr_details.get('title', 'N/A')}**

**Branches:**
- Source branch: `{branch_name}`
- Target branch: `{pr_details['base_branch']}`

**Status:** No merge conflicts detected.

Please provide:
1. A brief analysis of the changes in this PR
2. Key files that have been modified
3. Any suggestions for improvements or potential issues

Feel free to explore the codebase to better understand the changes."""

            else:
                # Issue Analysis Path (existing logic)
                issue_details = git_provider.get_issue_details(
                    token, workspace.github_repository, task.github_issue_number
                )

                if issue_details.get("error"):
                    return

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
                    content=f"Repository cloned to: {repo_path}\nCreated branch: {branch_name}\nAgent initialized and ready to work on the code.",
                    user_id=None,
                )
                db.add(system_message)
                db.commit()

                # Create automatic analysis request message for issue
                auto_message_content = f"""Please analyze this issue and provide an approach to implement the requested changes.

Issue: {issue_details.get('title', 'N/A')}

Provide:
1. A brief analysis of what needs to be done
2. Key files that may need to be modified
3. Your recommended approach to implement this

Feel free to read relevant files to better understand the codebase structure."""

        except git_local_service.GitLocalError as e:
            error_message = AgentMessage(
                workspace_task_id=task_id,
                role="system",
                content=f"Error initializing repository: {str(e)}",
                user_id=None,
            )
            db.add(error_message)
            db.commit()
            return

        # Save the automatic user message
        auto_user_message = AgentMessage(
            workspace_task_id=task_id,
            role="user",
            content=auto_message_content,
            user_id=None,  # System-generated message
        )
        db.add(auto_user_message)
        db.commit()
        db.refresh(auto_user_message)

        # Queue agent processing via Celery
        process_agent_response_task.delay(
            workspace_id,
            task_id,
            auto_user_message.id,
            token
        )

        # Record usage for auto-execution
        SubscriptionService.record_usage(
            db,
            task.added_by_user_id,
            EventType.AGENT_EXECUTION,
            workspace_id=workspace_id,
            resource_id=str(task_id),
        )

    except Exception as e:
        # Log error but don't fail the task creation
        print(f"Error in initial analysis for task {task_id}: {str(e)}")
    finally:
        db.close()


def _initialize_pr_task(
    workspace_id: int,
    task_id: int,
    pr_number: int,
    pr_details: dict,
    token: str
) -> None:
    """
    Initialize a task linked to an existing PR.

    This function runs in the background after a PR is linked and:
    1. Clones the repository
    2. Checks out the PR's branch
    3. Provides PR context (description, reviews, conflicts) to the agent
    4. Creates a new conversation ready for further changes
    """
    from app.database import SessionLocal
    from app.services import git_local_service
    from app.services.git_providers import get_git_provider_for_workspace as _get_ws_provider

    db = SessionLocal()

    try:
        # Get workspace and task
        from app.models.workspace import Workspace
        workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
        task = db.query(WorkspaceTask).filter(WorkspaceTask.id == task_id).first()

        if not workspace or not task:
            return

        git_provider = _get_ws_provider(workspace)

        # Generate task-specific repository path
        repo_path = git_local_service.get_task_repo_path(workspace_id, task_id)

        try:
            # Clone repository using provider-specific clone URL
            clone_url = git_provider.get_clone_url(workspace.github_repository, token)
            git_local_service.ensure_repo_cloned(
                repo_path, workspace.github_repository, token, auth_clone_url=clone_url
            )

            # Checkout the PR's branch
            branch_name = pr_details["head_branch"]

            # Check if branch exists locally
            if not git_local_service.branch_exists(repo_path, branch_name):
                # Fetch the PR directly using GitHub's PR refs
                # This works for both regular PRs and PRs from forks
                git_local_service.fetch_pull_request(repo_path, pr_number, branch_name)

            # Checkout the branch
            git_local_service.checkout_branch(repo_path, branch_name)

            # Update task with local repo path
            task.local_repo_path = repo_path
            db.commit()

            # Build PR context message with reviews and conflicts
            context_parts = [
                f"Linked to Pull Request #{pr_number}: {pr_details['title']}",
                f"Branch: {branch_name}",
                f"Repository cloned",
                f"\n## PR Description\n{pr_details.get('body', 'No description provided.')}"
            ]

            # Add review information if available
            reviews = pr_details.get("reviews", [])
            if reviews:
                context_parts.append("\n## PR Reviews")
                for review in reviews:
                    state_emoji = {"APPROVED": "✅", "CHANGES_REQUESTED": "🔴", "COMMENTED": "💬"}.get(review["state"], "")
                    context_parts.append(f"- {state_emoji} {review['user']} ({review['state']}): {review['body']}")

            # Add review comments (inline code comments) if available
            review_comments = pr_details.get("review_comments", [])
            if review_comments:
                context_parts.append("\n## Code Review Comments")
                for comment in review_comments[:10]:  # Limit to first 10 to avoid too much text
                    context_parts.append(f"- {comment['user']} on {comment['path']}: {comment['body']}")
                if len(review_comments) > 10:
                    context_parts.append(f"... and {len(review_comments) - 10} more comments")

            # Add merge conflict warning if applicable
            if pr_details.get("has_conflicts"):
                context_parts.append("\n⚠️ **This PR has merge conflicts that need to be resolved.**")
                context_parts.append(f"Mergeable state: {pr_details.get('mergeable_state', 'unknown')}")

            # Create system message with PR context
            system_message = AgentMessage(
                workspace_task_id=task_id,
                role="system",
                content="\n".join(context_parts),
                user_id=None,
            )
            db.add(system_message)
            db.commit()

            # Create welcoming user message
            welcome_message = AgentMessage(
                workspace_task_id=task_id,
                role="system",
                content="""Agent initialized and ready to work on this PR.

You can now:
- Request specific changes or improvements
- Ask to resolve merge conflicts
- Add new features or fix bugs
- Address review comments

Feel free to explore the codebase and make changes as needed.""",
                user_id=None,
            )
            db.add(welcome_message)
            db.commit()

        except git_local_service.GitLocalError as e:
            error_message = AgentMessage(
                workspace_task_id=task_id,
                role="system",
                content=f"Error initializing repository for PR: {str(e)}",
                user_id=None,
            )
            db.add(error_message)
            db.commit()
            return

    except Exception as e:
        # Log error but don't fail the task creation
        print(f"Error initializing PR task {task_id}: {str(e)}")
    finally:
        db.close()


@router.get("/{workspace_id}/tasks", response_model=WorkspaceTaskListResponse)
def list_workspace_tasks(
    workspace_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    skip: int = 0,
    limit: int = 100,
):
    """
    List all tasks (linked GitHub issues) for a workspace.

    Any workspace member can view tasks.

    Args:
        workspace_id: Workspace ID
        db: Database session
        current_user: Current authenticated user
        skip: Number of records to skip (pagination)
        limit: Maximum number of records to return

    Returns:
        List of tasks with issue URLs

    Raises:
        HTTPException: If user is not a workspace member
    """
    workspace, _ = get_workspace_or_403(workspace_id, db, current_user)

    # Query tasks with user details for "added_by"
    tasks_query = (
        db.query(WorkspaceTask, User)
        .join(User, WorkspaceTask.added_by_user_id == User.id)
        .filter(WorkspaceTask.workspace_id == workspace_id)
        .order_by(WorkspaceTask.added_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    tasks = []
    for task, user in tasks_query:
        tasks.append(
            WorkspaceTaskResponse(
                id=task.id,
                workspace_id=task.workspace_id,
                github_issue_number=task.github_issue_number,
                github_issue_title=task.github_issue_title,
                issue_url=task.get_issue_url(workspace.github_repository, getattr(workspace, 'git_provider', 'github'), getattr(workspace, 'gitlab_url', None)),
                added_by_user_id=task.added_by_user_id,
                added_by_username=user.username,
                added_at=task.added_at,
                agent_status=task.agent_status,
                agent_branch_name=task.agent_branch_name,
                agent_pr_number=task.agent_pr_number,
                agent_pr_url=task.agent_pr_url,
                agent_error=task.agent_error,
                agent_executed_at=task.agent_executed_at,
            )
        )

    total = db.query(WorkspaceTask).filter(WorkspaceTask.workspace_id == workspace_id).count()

    return WorkspaceTaskListResponse(tasks=tasks, total=total)


@router.get("/{workspace_id}/tasks/{task_id}", response_model=WorkspaceTaskResponse)
def get_workspace_task(
    workspace_id: int,
    task_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Get a single workspace task by ID.

    Any workspace member can view task details.

    Args:
        workspace_id: Workspace ID
        task_id: Task ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        Task details with issue URL

    Raises:
        HTTPException: If user is not a workspace member or task not found
    """
    workspace, _ = get_workspace_or_403(workspace_id, db, current_user)

    # Query task with user details
    result = (
        db.query(WorkspaceTask, User)
        .join(User, WorkspaceTask.added_by_user_id == User.id)
        .filter(WorkspaceTask.workspace_id == workspace_id, WorkspaceTask.id == task_id)
        .first()
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found in this workspace",
        )

    task, user = result

    return WorkspaceTaskResponse(
        id=task.id,
        workspace_id=task.workspace_id,
        github_issue_number=task.github_issue_number,
        github_issue_title=task.github_issue_title,
        issue_url=task.get_issue_url(workspace.github_repository, getattr(workspace, 'git_provider', 'github'), getattr(workspace, 'gitlab_url', None)),
        added_by_user_id=task.added_by_user_id,
        added_by_username=user.username,
        added_at=task.added_at,
        agent_status=task.agent_status,
        agent_branch_name=task.agent_branch_name,
        agent_pr_number=task.agent_pr_number,
        agent_pr_url=task.agent_pr_url,
        agent_error=task.agent_error,
        agent_executed_at=task.agent_executed_at,
    )


@router.post("/{workspace_id}/tasks", response_model=WorkspaceTaskResponse, status_code=status.HTTP_201_CREATED)
def add_workspace_task(
    workspace_id: int,
    task_data: WorkspaceTaskCreate,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Link a GitHub issue to workspace as a task.

    Any workspace member can add tasks.
    Validates that the issue exists in the workspace's GitHub repository.

    Args:
        workspace_id: Workspace ID
        task_data: Task creation data (issue number)
        db: Database session
        current_user: Current authenticated user

    Returns:
        Created task record

    Raises:
        HTTPException: If user lacks permission, issue doesn't exist, or already linked
    """
    workspace, _ = get_workspace_or_403(workspace_id, db, current_user)

    # Get token and provider for workspace
    token = get_workspace_github_token_or_403(db, workspace, current_user)
    git_provider = get_git_provider_for_workspace(workspace)

    # Validate issue exists
    validation = git_provider.validate_issue_exists(
        token, workspace.github_repository, task_data.github_issue_number
    )

    if not validation["exists"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=validation.get("error", f"Issue #{task_data.github_issue_number} not found"),
        )

    # Extract issue title from validation response
    issue_title = validation.get("issue_title")

    # Check if already linked
    existing = (
        db.query(WorkspaceTask)
        .filter(
            WorkspaceTask.workspace_id == workspace_id,
            WorkspaceTask.github_issue_number == task_data.github_issue_number,
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Issue #{task_data.github_issue_number} is already linked to this workspace",
        )

    # Create task
    task = WorkspaceTask(
        workspace_id=workspace_id,
        github_issue_number=task_data.github_issue_number,
        github_issue_title=issue_title,
        added_by_user_id=current_user.id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    # Trigger automatic analysis in the background
    background_tasks.add_task(
        _trigger_initial_analysis,
        workspace_id,
        task.id,
        token
    )

    return WorkspaceTaskResponse(
        id=task.id,
        workspace_id=task.workspace_id,
        github_issue_number=task.github_issue_number,
        github_issue_title=task.github_issue_title,
        issue_url=task.get_issue_url(workspace.github_repository, getattr(workspace, 'git_provider', 'github'), getattr(workspace, 'gitlab_url', None)),
        added_by_user_id=task.added_by_user_id,
        added_by_username=current_user.username,
        added_at=task.added_at,
        agent_status=task.agent_status,
        agent_branch_name=task.agent_branch_name,
        agent_pr_number=task.agent_pr_number,
        agent_pr_url=task.agent_pr_url,
        agent_error=task.agent_error,
        agent_executed_at=task.agent_executed_at,
    )


@router.delete("/{workspace_id}/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_workspace_task(
    workspace_id: int,
    task_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Remove a task (unlink GitHub issue) from workspace.

    Any workspace member can remove tasks.

    Args:
        workspace_id: Workspace ID
        task_id: Task ID to remove
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

    db.delete(task)
    db.commit()


@router.get("/{workspace_id}/available-issues", response_model=AvailableIssuesResponse)
def list_available_issues(
    workspace_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    state: str = Query("open", regex="^(open|closed|all)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
):
    """
    List available GitHub issues from the workspace's repository.

    Used for browsing issues to link. Shows which issues are already linked.
    Any workspace member can browse issues.

    Args:
        workspace_id: Workspace ID
        db: Database session
        current_user: Current authenticated user
        state: Issue state filter - "open", "closed", or "all"
        page: Page number for pagination
        per_page: Number of issues per page (max 100)

    Returns:
        List of available issues with indication of already linked ones

    Raises:
        HTTPException: If user lacks permission or GitHub API error
    """
    workspace, _ = get_workspace_or_403(workspace_id, db, current_user)

    # Get token and provider for workspace
    token = get_workspace_github_token_or_403(db, workspace, current_user)
    git_provider = get_git_provider_for_workspace(workspace)

    # List issues from provider
    issues_result = git_provider.list_issues(token, workspace.github_repository, state, per_page, page,
                                             skip_cache=False)

    if issues_result.get("error"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=issues_result["error"],
        )

    # Get already linked issue numbers for this workspace
    linked_tasks = db.query(WorkspaceTask.github_issue_number).filter(
        WorkspaceTask.workspace_id == workspace_id
    ).all()
    already_linked = [task.github_issue_number for task in linked_tasks]

    # Convert to response format
    issues = [GitHubIssuePreview(**issue) for issue in issues_result["issues"]]

    return AvailableIssuesResponse(
        repository=workspace.github_repository,
        issues=issues,
        total_count=issues_result["total_count"],
        has_next=issues_result["has_next"],
        already_linked=already_linked,
    )


@router.post(
    "/{workspace_id}/tasks/{task_id}/create-pr",
    response_model=dict,
    status_code=status.HTTP_200_OK,
)
def create_pull_request_from_task(
    workspace_id: int,
    task_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    assignee_username: Annotated[str | None, Query()] = None,
    draft: Annotated[bool, Query()] = True,
):
    """
    Create a pull request from a task's agent branch to the development branch.

    This endpoint:
    1. Verifies the task has an agent branch
    2. Creates a PR from the agent branch to the dev branch
    3. Optionally assigns a user to the PR
    4. Updates the task with PR information

    Args:
        workspace_id: Workspace ID
        task_id: Task ID
        db: Database session
        current_user: Current authenticated user
        assignee_username: GitHub username to assign the PR to (optional)
        draft: Create as draft PR (default: True)

    Returns:
        dict with PR information:
        {
            "success": bool,
            "pr_number": int | None,
            "pr_url": str | None,
            "message": str
        }

    Raises:
        HTTPException: If user lacks permission, task not found, or PR creation fails
    """
    from app.models.workspace import Workspace

    # Verify workspace access
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

    # Check if task has an agent branch
    if not task.agent_branch_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Task does not have an agent branch. Please ensure the agent has made changes first.",
        )

    # ============================================================
    # CHECK FOR EXISTING PR ON GITHUB (not just in local task record)
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
            # PR is already open - update task record and return existing PR info
            pr_number = existing_pr["number"]
            pr_url = existing_pr["html_url"]

            # Update task with existing PR info if not already set
            if not task.agent_pr_number:
                task.agent_pr_number = pr_number
                task.agent_pr_url = pr_url
                db.commit()

            # Fetch latest comments on the PR
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
                "message": f"Found existing open PR #{pr_number}. No new PR created.",
                "latest_comments": comments_result.get("comments", [])[-5:] if comments_result.get("comments") else []
            }

        elif pr_state == "closed":
            # PR was closed without merging - we can create a fresh PR on the same branch
            task.agent_pr_number = None
            task.agent_pr_url = None
            db.commit()

    # If task already has PR number but not found on GitHub, reset it
    elif task.agent_pr_number:
        task.agent_pr_number = None
        task.agent_pr_url = None
        db.commit()

    # Get issue details for PR title and body
    issue_details = git_provider.get_issue_details(
        token, workspace.github_repository, task.github_issue_number
    )

    if issue_details.get("error"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to fetch issue details: {issue_details['error']}",
        )

    # Build PR title and body
    pr_title = f"Fix #{task.github_issue_number}: {issue_details['title']}"
    pr_body = f"""This PR addresses issue #{task.github_issue_number}.

## Issue Description
{issue_details.get('body', 'No description provided.')}

## Changes
{f"Branch: `{task.agent_branch_name}`"}

---
🤖 Generated by Avery Agent
Fixes #{task.github_issue_number}
"""

    # Prepare assignees list
    assignees = [assignee_username] if assignee_username else None

    # Create the pull request
    pr_result = git_provider.create_pull_request(
        token=token,
        repo=workspace.github_repository,
        head=task.agent_branch_name,
        base=workspace.github_dev_branch,
        title=pr_title,
        body=pr_body,
        draft=draft,
        assignees=assignees,
    )

    if not pr_result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create pull request: {pr_result['error']}",
        )

    # Update task with PR information
    task.agent_pr_number = pr_result["pr_number"]
    task.agent_pr_url = pr_result["pr_url"]
    db.commit()

    return {
        "success": True,
        "pr_number": pr_result["pr_number"],
        "pr_url": pr_result["pr_url"],
        "message": f"Pull request #{pr_result['pr_number']} created successfully" + (f" and assigned to {assignee_username}" if assignee_username else ""),
    }


@router.post("/{workspace_id}/feature-requests", response_model=FeatureRequestResponse, status_code=status.HTTP_201_CREATED)
def create_feature_request(
    workspace_id: int,
    feature_request: FeatureRequestCreate,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Create a new feature request as a GitHub issue and optionally link it as a task.

    This endpoint:
    1. Checks for similar existing issues to prevent duplicates
    2. Creates a GitHub issue in the workspace repository
    3. Optionally links the issue as a workspace task
    4. Triggers automatic agent analysis if linked

    Args:
        workspace_id: Workspace ID
        feature_request: Feature request data (title, description, etc.)
        background_tasks: FastAPI background tasks
        db: Database session
        current_user: Current authenticated user

    Returns:
        FeatureRequestResponse with issue number, URL, and optional task ID

    Raises:
        HTTPException: If workspace not found, no GitHub access, or issue creation fails
    """
    # Get workspace and verify permissions
    workspace, _ = get_workspace_or_403(workspace_id, db, current_user)

    # Get token and provider for workspace
    token = get_workspace_github_token_or_403(db, workspace, current_user)
    git_provider = get_git_provider_for_workspace(workspace)

    # Build issue body with feature request details
    issue_body = f"{feature_request.description}\n\n"

    if feature_request.acceptance_criteria:
        issue_body += f"## Acceptance Criteria\n{feature_request.acceptance_criteria}\n\n"

    issue_body += "---\n*Created via LaunchPilot Feature Request*"

    # Create issue via provider
    result = git_provider.create_issue(
        token=token,
        repo=workspace.github_repository,
        title=feature_request.title,
        body=issue_body,
        labels=feature_request.labels,
        assignees=None,  # Don't auto-assign
    )

    if not result["success"]:
        return FeatureRequestResponse(
            success=False,
            error=result["error"],
        )

    # If link_as_task is True, create the workspace task
    task_id = None
    if feature_request.link_as_task:
        try:
            # Create task record
            new_task = WorkspaceTask(
                workspace_id=workspace_id,
                github_issue_number=result["issue_number"],
                github_issue_title=feature_request.title,
                added_by_user_id=current_user.id,
            )
            db.add(new_task)
            db.commit()
            db.refresh(new_task)

            task_id = new_task.id

            # Trigger background initialization (clone repo, create branch, analyze)
            background_tasks.add_task(
                _trigger_initial_analysis,
                workspace_id=workspace_id,
                task_id=new_task.id,
                token=token,
            )

        except Exception as e:
            # Issue was created successfully but task linking failed
            # Return success with issue details but no task_id
            return FeatureRequestResponse(
                success=True,
                issue_number=result["issue_number"],
                issue_url=result["issue_url"],
                task_id=None,
                error=f"Issue created but failed to link as task: {str(e)}",
            )

    return FeatureRequestResponse(
        success=True,
        issue_number=result["issue_number"],
        issue_url=result["issue_url"],
        task_id=task_id,
    )


@router.post("/{workspace_id}/search-similar-issues", response_model=SimilarIssuesResponse)
def search_similar_feature_requests(
    workspace_id: int,
    search_params: SimilarIssuesSearch,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Search for similar existing issues to prevent duplicate feature requests.

    Args:
        workspace_id: Workspace ID
        search_params: Search parameters (query, state, max_results)
        db: Database session
        current_user: Current authenticated user

    Returns:
        SimilarIssuesResponse with matching issues

    Raises:
        HTTPException: If workspace not found or no GitHub access
    """
    # Get workspace and verify permissions
    workspace, _ = get_workspace_or_403(workspace_id, db, current_user)

    # Get token and provider for workspace
    token = get_workspace_github_token_or_403(db, workspace, current_user)
    git_provider = get_git_provider_for_workspace(workspace)

    # Search for similar issues
    result = git_provider.search_similar_issues(
        token=token,
        repo=workspace.github_repository,
        query=search_params.query,
        state=search_params.state,
        max_results=search_params.max_results,
    )

    # Convert to response format
    issues = [
        GitHubIssuePreview(
            number=issue["number"],
            title=issue["title"],
            state=issue["state"],
            html_url=issue["html_url"],
            created_at=issue["created_at"],
            updated_at=issue.get("updated_at", issue["created_at"]),
        )
        for issue in result.get("issues", [])
    ]

    return SimilarIssuesResponse(
        repository=result.get("repository", workspace.github_repository),
        issues=issues,
        total_count=result.get("total_count", 0),
        error=result.get("error"),
    )


@router.get("/{workspace_id}/pull-requests", response_model=dict)
def list_workspace_pull_requests(
    workspace_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    state: str = Query("open", regex="^(open|closed|all)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
):
    """
    List pull requests from the workspace's repository.

    Used for browsing PRs to link. Any workspace member can browse PRs.

    Args:
        workspace_id: Workspace ID
        db: Database session
        current_user: Current authenticated user
        state: PR state filter - "open", "closed", or "all"
        page: Page number for pagination
        per_page: Number of PRs per page (max 100)

    Returns:
        List of pull requests with details

    Raises:
        HTTPException: If user lacks permission or GitHub API error
    """
    workspace, _ = get_workspace_or_403(workspace_id, db, current_user)

    # Get token and provider for workspace
    token = get_workspace_github_token_or_403(db, workspace, current_user)
    git_provider = get_git_provider_for_workspace(workspace)

    # List pull requests from provider
    prs_result = git_provider.list_pull_requests(
        token, workspace.github_repository, state, per_page, page, skip_cache=True
    )

    if prs_result.get("error"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=prs_result["error"],
        )

    return prs_result


@router.post(
    "/{workspace_id}/link-pr",
    response_model=WorkspaceTaskResponse,
    status_code=status.HTTP_201_CREATED,
)
def link_pull_request_to_workspace(
    workspace_id: int,
    pr_number: int = Query(..., description="Pull request number to link"),
    auto_analyze: bool = Query(True, description="Automatically trigger conflict analysis"),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Link an existing pull request to workspace and create a new task for agent changes.

    This endpoint:
    1. Fetches PR details including reviews, comments, and merge conflicts
    2. Creates a new workspace task linked to the PR
    3. Auto-switches to the PR's branch
    4. Initializes agent with PR context (description, reviews, conflicts)
    5. Optionally triggers automatic conflict analysis if auto_analyze=true
    6. Creates a new conversation for making further changes

    Args:
        workspace_id: Workspace ID
        pr_number: Pull request number to link
        auto_analyze: If true, automatically triggers agent analysis for conflicts
        background_tasks: FastAPI background tasks
        db: Database session
        current_user: Current authenticated user

    Returns:
        WorkspaceTaskResponse with newly created task details

    Raises:
        HTTPException: If user lacks permission, PR not found, or already linked
    """
    from app.models.workspace import Workspace
    from app.services import git_local_service
    from pathlib import Path

    # Verify workspace access
    workspace, _ = get_workspace_or_403(workspace_id, db, current_user)

    # Get token and provider for workspace
    token = get_workspace_github_token_or_403(db, workspace, current_user)
    git_provider = get_git_provider_for_workspace(workspace)

    # Get PR details including reviews and conflicts
    pr_details = git_provider.get_pull_request_details(token, workspace.github_repository, pr_number)

    if pr_details.get("error"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to fetch PR details: {pr_details['error']}",
        )

    # Check if PR is already linked to a task
    existing_task = (
        db.query(WorkspaceTask)
        .filter(
            WorkspaceTask.workspace_id == workspace_id,
            WorkspaceTask.agent_pr_number == pr_number,
        )
        .first()
    )

    if existing_task:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Pull request #{pr_number} is already linked to task #{existing_task.id}",
        )

    # Create new workspace task with PR information
    # Use PR number as a placeholder for github_issue_number (since no specific issue)
    task = WorkspaceTask(
        workspace_id=workspace_id,
        github_issue_number=pr_number,  # Store PR number here
        github_issue_title=f"PR #{pr_number}: {pr_details['title']}",
        added_by_user_id=current_user.id,
        agent_branch_name=pr_details["head_branch"],
        agent_pr_number=pr_number,
        agent_pr_url=pr_details["html_url"],
        agent_status="active",
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    # Choose initialization method based on auto_analyze parameter
    if auto_analyze:
        # Use automatic analysis - triggers agent to analyze and resolve conflicts
        background_tasks.add_task(
            _trigger_initial_analysis,
            workspace_id,
            task.id,
            token,
            pr_number
        )
    else:
        # Use basic initialization - just provides PR context
        background_tasks.add_task(
            _initialize_pr_task,
            workspace_id,
            task.id,
            pr_number,
            pr_details,
            token
        )

    return WorkspaceTaskResponse(
        id=task.id,
        workspace_id=task.workspace_id,
        github_issue_number=task.github_issue_number,
        github_issue_title=task.github_issue_title,
        issue_url=task.get_issue_url(workspace.github_repository, getattr(workspace, 'git_provider', 'github'), getattr(workspace, 'gitlab_url', None)),
        added_by_user_id=task.added_by_user_id,
        added_by_username=current_user.username,
        added_at=task.added_at,
        agent_status=task.agent_status,
        agent_branch_name=task.agent_branch_name,
        agent_pr_number=task.agent_pr_number,
        agent_pr_url=task.agent_pr_url,
        agent_error=task.agent_error,
        agent_executed_at=task.agent_executed_at,
    )


@router.post(
    "/{workspace_id}/tasks/{task_id}/analyze-pr",
    response_model=dict,
    status_code=status.HTTP_200_OK,
)
def trigger_pr_analysis(
    workspace_id: int,
    task_id: int,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Trigger automatic PR analysis for a linked PR task.

    This endpoint triggers the agent to analyze the PR for:
    - Merge conflicts with the base branch
    - Code changes and their impact
    - Recommendations for conflict resolution

    This is useful for:
    - Re-analyzing a PR after changes to the base branch
    - Triggering analysis on a PR that was linked without auto_analyze
    - Getting fresh conflict analysis

    Args:
        workspace_id: Workspace ID
        task_id: Task ID (must be linked to a PR)
        background_tasks: FastAPI background tasks
        db: Database session
        current_user: Current authenticated user

    Returns:
        dict with success status and message

    Raises:
        HTTPException: If task not found, not a PR task, or no GitHub access
    """
    # Verify workspace access
    workspace, _ = get_workspace_or_403(workspace_id, db, current_user)

    # Get GitHub token using workspace-level strategy (uses owner's token for shared access)
    token = get_workspace_github_token_or_403(db, workspace, current_user)

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

    # Verify this is a PR task
    if not task.agent_pr_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This task is not linked to a Pull Request. Only PR-linked tasks can be analyzed.",
        )

    # Trigger analysis in background
    background_tasks.add_task(
        _trigger_initial_analysis,
        workspace_id,
        task_id,
        token,
        task.agent_pr_number
    )

    return {
        "success": True,
        "message": f"PR analysis triggered for task #{task_id} (PR #{task.agent_pr_number}). The agent will analyze the PR and check for conflicts.",
        "task_id": task_id,
        "pr_number": task.agent_pr_number,
    }
