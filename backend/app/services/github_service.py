"""GitHub API integration service using PyGithub."""

import logging
import time
from typing import Any

import httpx
from github import Auth, Github, GithubException

logger = logging.getLogger(__name__)


# Simple in-memory cache with TTL
_cache: dict[str, tuple[Any, float]] = {}
CACHE_TTL = 900  # 15 minutes in seconds


def _get_from_cache(key: str) -> Any | None:
    """Get value from cache if not expired."""
    if key in _cache:
        value, timestamp = _cache[key]
        if time.time() - timestamp < CACHE_TTL:
            return value
        else:
            del _cache[key]
    return None


def _set_cache(key: str, value: Any) -> None:
    """Set value in cache with current timestamp."""
    _cache[key] = (value, time.time())


def get_github_client(token: str) -> Github:
    """
    Create authenticated GitHub client.

    Args:
        token: GitHub personal access token

    Returns:
        Authenticated GitHub client instance
    """
    auth = Auth.Token(token)
    return Github(auth=auth)


def format_github_error(e: GithubException, context: str = "") -> str:
    """
    Format GitHub API error with actionable guidance.

    Args:
        e: GithubException from PyGithub
        context: Additional context about the operation

    Returns:
        User-friendly error message with guidance
    """
    status = e.status

    if status == 401:
        return "Authentication failed. Your GitHub token may be invalid or expired. Please reconnect your GitHub account."

    elif status == 403:
        # Check if it's a rate limit error
        if "rate limit" in str(e).lower() or "API rate limit exceeded" in str(e):
            return "GitHub API rate limit exceeded. Please wait a few minutes and try again, or use a different GitHub account with a higher rate limit."

        # Check for insufficient permissions
        if "Resource not accessible" in str(e) or "permission" in str(e).lower():
            return f"Insufficient permissions. Please ensure your GitHub token has the required 'repo' scope with read/write access. {context}"

        # Check for SAML/SSO requirement
        if "SAML" in str(e) or "SSO" in str(e):
            return "This repository requires SSO authorization. Please authorize your token for SSO access in GitHub settings."

        return "Access forbidden. This could be due to: (1) Rate limit exceeded, (2) Insufficient token permissions, or (3) SSO authorization required."

    elif status == 404:
        return f"Resource not found. This could mean: (1) The repository doesn't exist, (2) You don't have access to it, or (3) Your token lacks the necessary permissions. {context}"

    elif status == 422:
        # Validation error - extract specific message if available
        try:
            error_data = e.data
            if isinstance(error_data, dict):
                if "errors" in error_data and error_data["errors"]:
                    specific_errors = [err.get("message", "") for err in error_data["errors"]]
                    return f"Validation failed: {', '.join(specific_errors)}"
                elif "message" in error_data:
                    return f"Validation failed: {error_data['message']}"
        except:
            pass
        return "Validation failed. Please check that all provided values (labels, assignees, etc.) are valid."

    elif status == 500:
        return "GitHub server error. This is a temporary issue on GitHub's side. Please try again in a few moments."

    elif status == 503:
        return "GitHub service unavailable. The service is temporarily down. Please try again later."

    else:
        # Try to extract message from exception
        try:
            if hasattr(e, 'data') and isinstance(e.data, dict) and 'message' in e.data:
                return f"GitHub API error: {e.data['message']}"
        except:
            pass

        return f"GitHub API error (status {status}). {str(e) if str(e) else 'Unknown error occurred.'}"


def validate_repository(token: str, repo: str) -> dict:
    """
    Validate that repository exists and user has access.

    Args:
        token: GitHub personal access token
        repo: Repository in format "owner/repo"

    Returns:
        dict with validation result:
        {
            "valid": bool,
            "repository": str,
            "description": str | None,
            "default_branch": str | None,
            "error": str | None
        }
    """
    cache_key = f"repo:{hash(token)}:{repo}"
    cached = _get_from_cache(cache_key)
    if cached:
        return cached

    try:
        github = get_github_client(token)
        repository = github.get_repo(repo)

        result = {
            "valid": True,
            "repository": repo,
            "description": repository.description,
            "default_branch": repository.default_branch,
            "error": None
        }

        _set_cache(cache_key, result)
        return result

    except GithubException as e:
        error_msg = format_github_error(e, f"Ensure you have access to repository '{repo}'.")
        return {
            "valid": False,
            "repository": repo,
            "description": None,
            "default_branch": None,
            "error": error_msg
        }

    except Exception as e:
        return {
            "valid": False,
            "repository": repo,
            "description": None,
            "default_branch": None,
            "error": f"Unexpected error: {str(e)}"
        }


def list_branches(token: str, repo: str, skip_cache: bool = False) -> dict:
    """
    List all branches for a repository.

    Args:
        token: GitHub personal access token
        repo: Repository in format "owner/repo"
        skip_cache: If True, bypass cache and fetch fresh data

    Returns:
        dict with branch list:
        {
            "repository": str,
            "branches": list[str],
            "error": str | None
        }
    """
    cache_key = f"branches:{hash(token)}:{repo}"

    if not skip_cache:
        cached = _get_from_cache(cache_key)
        if cached:
            return cached

    try:
        github = get_github_client(token)
        repository = github.get_repo(repo)
        branches = [branch.name for branch in repository.get_branches()]

        result = {
            "repository": repo,
            "branches": branches,
            "error": None
        }

        _set_cache(cache_key, result)
        return result

    except GithubException as e:
        error_msg = format_github_error(e, f"Unable to list branches for repository '{repo}'.")
        return {
            "repository": repo,
            "branches": [],
            "error": error_msg
        }

    except Exception as e:
        return {
            "repository": repo,
            "branches": [],
            "error": f"Unexpected error: {str(e)}"
        }


def validate_branch(token: str, repo: str, branch: str) -> bool:
    """
    Validate that a branch exists in the repository.

    Args:
        token: GitHub personal access token
        repo: Repository in format "owner/repo"
        branch: Branch name to validate

    Returns:
        True if branch exists, False otherwise
    """
    branches_result = list_branches(token, repo)

    if branches_result.get("error"):
        return False

    return branch in branches_result.get("branches", [])


def get_github_username(token: str) -> str | None:
    """
    Get the authenticated user's GitHub username.

    Args:
        token: GitHub personal access token

    Returns:
        GitHub username or None if failed
    """
    try:
        github = get_github_client(token)
        user = github.get_user()
        return user.login
    except Exception:
        return None


def list_issues(token: str, repo: str, state: str = "open", per_page: int = 50, page: int = 1, skip_cache: bool = False) -> dict:
    """
    List issues from a repository.

    Args:
        token: GitHub personal access token
        repo: Repository in format "owner/repo"
        state: Issue state - "open", "closed", or "all" (default: "open")
        per_page: Number of issues per page (max 100, default 50)
        page: Page number for pagination (default 1)
        skip_cache: If True, bypass cache and fetch fresh data (default: False)

    Returns:
        dict with issue list:
        {
            "repository": str,
            "issues": list[dict],  # [{number, title, state, html_url, created_at, updated_at, labels}]
            "total_count": int,
            "has_next": bool,
            "error": str | None
        }
    """
    cache_key = f"issues:{hash(token)}:{repo}:{state}:{page}"

    if not skip_cache:
        cached = _get_from_cache(cache_key)
        if cached:
            return cached

    try:
        github = get_github_client(token)
        repository = github.get_repo(repo)

        # Get issues with pagination (PyGithub uses 0-based indexing)
        issues_paginated = repository.get_issues(state=state)

        # Calculate start and end indices for pagination
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page

        # Convert to list and slice for pagination
        all_issues = []
        for idx, issue in enumerate(issues_paginated):
            if idx < start_idx:
                continue
            if idx >= end_idx:
                break

            # Skip pull requests (GitHub API returns PRs as issues)
            if issue.pull_request is not None:
                continue

            all_issues.append({
                "number": issue.number,
                "title": issue.title,
                "state": issue.state,
                "html_url": issue.html_url,
                "created_at": issue.created_at.isoformat(),
                "updated_at": issue.updated_at.isoformat(),
                "labels": [label.name for label in issue.labels],
            })

        # Check if there are more pages
        has_next = len(all_issues) == per_page

        result = {
            "repository": repo,
            "issues": all_issues,
            "total_count": repository.open_issues_count,
            "has_next": has_next,
            "error": None
        }

        _set_cache(cache_key, result)
        return result

    except GithubException as e:
        error_msg = format_github_error(e, f"Unable to list issues for repository '{repo}'.")
        return {
            "repository": repo,
            "issues": [],
            "total_count": 0,
            "has_next": False,
            "error": error_msg
        }

    except Exception as e:
        return {
            "repository": repo,
            "issues": [],
            "total_count": 0,
            "has_next": False,
            "error": f"Unexpected error: {str(e)}"
        }


def validate_issue_exists(token: str, repo: str, issue_number: int) -> dict:
    """
    Validate that a specific issue exists in the repository.

    Args:
        token: GitHub personal access token
        repo: Repository in format "owner/repo"
        issue_number: Issue number to validate

    Returns:
        dict with validation result:
        {
            "exists": bool,
            "issue_number": int,
            "issue_url": str | None,
            "issue_title": str | None,
            "error": str | None
        }
    """
    cache_key = f"issue:{hash(token)}:{repo}:{issue_number}"
    cached = _get_from_cache(cache_key)
    if cached:
        return cached

    try:
        github = get_github_client(token)
        repository = github.get_repo(repo)
        issue = repository.get_issue(issue_number)

        # Check if it's actually a pull request (we only want issues)
        if issue.pull_request is not None:
            return {
                "exists": False,
                "issue_number": issue_number,
                "issue_url": None,
                "issue_title": None,
                "error": f"#{issue_number} is a pull request, not an issue"
            }

        result = {
            "exists": True,
            "issue_number": issue_number,
            "issue_url": issue.html_url,
            "issue_title": issue.title,
            "error": None
        }

        _set_cache(cache_key, result)
        return result

    except GithubException as e:
        error_msg = format_github_error(e, f"Unable to validate issue #{issue_number} in repository '{repo}'.")
        return {
            "exists": False,
            "issue_number": issue_number,
            "issue_url": None,
            "issue_title": None,
            "error": error_msg
        }

    except Exception as e:
        return {
            "exists": False,
            "issue_number": issue_number,
            "issue_url": None,
            "issue_title": None,
            "error": f"Unexpected error: {str(e)}"
        }


def get_issue_details(token: str, repo: str, issue_number: int) -> dict:
    """
    Get full details of a GitHub issue including body and labels.

    Args:
        token: GitHub personal access token
        repo: Repository in format "owner/repo"
        issue_number: Issue number

    Returns:
        dict with issue details:
        {
            "number": int,
            "title": str,
            "body": str | None,
            "state": str,
            "labels": list[str],
            "html_url": str,
            "created_at": str,
            "updated_at": str,
            "error": str | None
        }
    """
    try:
        github = get_github_client(token)
        repository = github.get_repo(repo)
        issue = repository.get_issue(issue_number)

        # Check if it's a pull request
        if issue.pull_request is not None:
            return {
                "error": f"#{issue_number} is a pull request, not an issue"
            }

        return {
            "number": issue.number,
            "title": issue.title,
            "body": issue.body or "",
            "state": issue.state,
            "labels": [label.name for label in issue.labels],
            "html_url": issue.html_url,
            "created_at": issue.created_at.isoformat(),
            "updated_at": issue.updated_at.isoformat(),
            "error": None
        }

    except GithubException as e:
        error_msg = format_github_error(e, f"Unable to get details for issue #{issue_number}.")
        return {"error": error_msg}

    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


def get_repository_tree(token: str, repo: str, branch: str, path: str = "") -> dict:
    """
    Get file structure of repository at specific branch and path.

    Args:
        token: GitHub personal access token
        repo: Repository in format "owner/repo"
        branch: Branch name
        path: Directory path (default: root)

    Returns:
        dict with tree structure:
        {
            "tree": list[dict],  # [{path, type, size, sha}]
            "error": str | None
        }
    """
    try:
        github = get_github_client(token)
        repository = github.get_repo(repo)

        # Get the git tree recursively
        branch_obj = repository.get_branch(branch)
        tree = repository.get_git_tree(branch_obj.commit.sha, recursive=True)

        tree_items = []
        for item in tree.tree:
            # Filter by path if specified
            if path and not item.path.startswith(path):
                continue

            tree_items.append({
                "path": item.path,
                "type": item.type,  # blob, tree
                "size": item.size,
                "sha": item.sha
            })

        return {
            "tree": tree_items,
            "error": None
        }

    except GithubException as e:
        error_msg = format_github_error(e, f"Unable to get repository tree for branch '{branch}'.")
        return {"tree": [], "error": error_msg}

    except Exception as e:
        return {"tree": [], "error": f"Unexpected error: {str(e)}"}


def create_branch(token: str, repo: str, branch_name: str, base_branch: str) -> dict:
    """
    Create a new branch from base branch.

    Args:
        token: GitHub personal access token
        repo: Repository in format "owner/repo"
        branch_name: Name for the new branch
        base_branch: Branch to create from

    Returns:
        dict with result:
        {
            "success": bool,
            "branch_name": str,
            "sha": str | None,
            "error": str | None
        }
    """
    try:
        github = get_github_client(token)
        repository = github.get_repo(repo)

        # Get the base branch commit SHA
        base_ref = repository.get_git_ref(f"heads/{base_branch}")
        base_sha = base_ref.object.sha

        # Create the new branch
        repository.create_git_ref(f"refs/heads/{branch_name}", base_sha)

        return {
            "success": True,
            "branch_name": branch_name,
            "sha": base_sha,
            "error": None
        }

    except GithubException as e:
        error_msg = format_github_error(e, f"Unable to create branch '{branch_name}' from '{base_branch}'.")
        return {
            "success": False,
            "branch_name": branch_name,
            "sha": None,
            "error": error_msg
        }

    except Exception as e:
        return {
            "success": False,
            "branch_name": branch_name,
            "sha": None,
            "error": f"Unexpected error: {str(e)}"
        }


def get_file_content(token: str, repo: str, branch: str, file_path: str) -> dict:
    """
    Get content of a file from repository.

    Args:
        token: GitHub personal access token
        repo: Repository in format "owner/repo"
        branch: Branch name
        file_path: Path to file in repository

    Returns:
        dict with file content:
        {
            "content": str | None,
            "sha": str | None,  # File SHA needed for updates
            "encoding": str | None,
            "error": str | None
        }
    """
    try:
        github = get_github_client(token)
        repository = github.get_repo(repo)

        # Get file content
        content_file = repository.get_contents(file_path, ref=branch)

        # Decode content if it's a file (not a directory)
        if isinstance(content_file, list):
            return {"error": f"'{file_path}' is a directory, not a file"}

        return {
            "content": content_file.decoded_content.decode('utf-8'),
            "sha": content_file.sha,
            "encoding": content_file.encoding,
            "error": None
        }

    except GithubException as e:
        if e.status == 404:
            # File not found - this is OK for new files
            return {
                "content": None,
                "sha": None,
                "encoding": None,
                "error": None
            }

        error_msg = format_github_error(e, f"Unable to get content for file '{file_path}' on branch '{branch}'.")
        return {
            "content": None,
            "sha": None,
            "encoding": None,
            "error": error_msg
        }

    except Exception as e:
        return {
            "content": None,
            "sha": None,
            "encoding": None,
            "error": f"Unexpected error: {str(e)}"
        }


def create_or_update_file(
    token: str,
    repo: str,
    branch: str,
    file_path: str,
    content: str,
    message: str,
    sha: str | None = None
) -> dict:
    """
    Create or update a file in the repository.

    Args:
        token: GitHub personal access token
        repo: Repository in format "owner/repo"
        branch: Branch name
        file_path: Path to file in repository
        content: File content
        message: Commit message
        sha: File SHA if updating existing file (None for new files)

    Returns:
        dict with result:
        {
            "success": bool,
            "commit_sha": str | None,
            "error": str | None
        }
    """
    try:
        github = get_github_client(token)
        repository = github.get_repo(repo)

        if sha:
            # Update existing file
            result = repository.update_file(
                path=file_path,
                message=message,
                content=content,
                sha=sha,
                branch=branch
            )
        else:
            # Create new file
            result = repository.create_file(
                path=file_path,
                message=message,
                content=content,
                branch=branch
            )

        return {
            "success": True,
            "commit_sha": result["commit"].sha,
            "error": None
        }

    except GithubException as e:
        error_msg = format_github_error(e, f"Unable to create/update file '{file_path}' on branch '{branch}'.")
        return {
            "success": False,
            "commit_sha": None,
            "error": error_msg
        }

    except Exception as e:
        return {
            "success": False,
            "commit_sha": None,
            "error": f"Unexpected error: {str(e)}"
        }


def create_pull_request(
    token: str,
    repo: str,
    head: str,
    base: str,
    title: str,
    body: str,
    draft: bool = True,
    assignees: list[str] | None = None
) -> dict:
    """
    Create a pull request.

    Args:
        token: GitHub personal access token
        repo: Repository in format "owner/repo"
        head: Branch name with changes
        base: Branch to merge into
        title: PR title
        body: PR description
        draft: Create as draft PR (default: True)
        assignees: List of GitHub usernames to assign (optional)

    Returns:
        dict with result:
        {
            "success": bool,
            "pr_number": int | None,
            "pr_url": str | None,
            "error": str | None
        }
    """
    try:
        github = get_github_client(token)
        repository = github.get_repo(repo)

        # Create the pull request
        pr = repository.create_pull(
            title=title,
            body=body,
            head=head,
            base=base,
            draft=draft
        )

        # Assign users if specified
        if assignees:
            try:
                pr.add_to_assignees(*assignees)
            except GithubException as e:
                # Don't fail the entire PR creation if assignment fails
                logger.warning(f"Failed to assign users to PR: {str(e)}")

        return {
            "success": True,
            "pr_number": pr.number,
            "pr_url": pr.html_url,
            "error": None
        }

    except GithubException as e:
        error_msg = format_github_error(e, f"Unable to create pull request from '{head}' to '{base}'.")
        return {
            "success": False,
            "pr_number": None,
            "pr_url": None,
            "error": error_msg
        }

    except Exception as e:
        return {
            "success": False,
            "pr_number": None,
            "pr_url": None,
            "error": f"Unexpected error: {str(e)}"
        }


def add_pr_comment(
    token: str,
    repo: str,
    pr_number: int,
    comment: str
) -> dict:
    """
    Add a comment to a pull request.

    Args:
        token: GitHub personal access token
        repo: Repository in format "owner/repo"
        pr_number: Pull request number
        comment: Comment text (markdown supported)

    Returns:
        dict with result:
        {
            "success": bool,
            "comment_id": int | None,
            "comment_url": str | None,
            "error": str | None
        }
    """
    try:
        github = get_github_client(token)
        repository = github.get_repo(repo)

        # Get the PR and add comment
        pr = repository.get_pull(pr_number)
        comment_obj = pr.create_issue_comment(comment)

        return {
            "success": True,
            "comment_id": comment_obj.id,
            "comment_url": comment_obj.html_url,
            "error": None
        }

    except GithubException as e:
        error_msg = format_github_error(e, f"Unable to add comment to PR #{pr_number}.")
        return {
            "success": False,
            "comment_id": None,
            "comment_url": None,
            "error": error_msg
        }

    except Exception as e:
        return {
            "success": False,
            "comment_id": None,
            "comment_url": None,
            "error": f"Unexpected error: {str(e)}"
        }


def create_issue(
    token: str,
    repo: str,
    title: str,
    body: str,
    labels: list[str] | None = None,
    assignees: list[str] | None = None
) -> dict:
    """
    Create a new GitHub issue.

    Args:
        token: GitHub personal access token
        repo: Repository in format "owner/repo"
        title: Issue title
        body: Issue description/body
        labels: List of label names to apply (optional)
        assignees: List of GitHub usernames to assign (optional)

    Returns:
        dict with result:
        {
            "success": bool,
            "issue_number": int | None,
            "issue_url": str | None,
            "error": str | None
        }
    """
    try:
        github = get_github_client(token)
        repository = github.get_repo(repo)

        # Create the issue
        issue = repository.create_issue(
            title=title,
            body=body,
            labels=labels or [],
            assignees=assignees or []
        )

        return {
            "success": True,
            "issue_number": issue.number,
            "issue_url": issue.html_url,
            "error": None
        }

    except GithubException as e:
        error_msg = format_github_error(e, "Make sure your token has 'repo' scope to create issues.")
        return {
            "success": False,
            "issue_number": None,
            "issue_url": None,
            "error": error_msg
        }

    except Exception as e:
        return {
            "success": False,
            "issue_number": None,
            "issue_url": None,
            "error": f"Unexpected error: {str(e)}"
        }


def search_similar_issues(
    token: str,
    repo: str,
    query: str,
    state: str = "open",
    max_results: int = 5
) -> dict:
    """
    Search for similar issues in a repository using GitHub search.

    Args:
        token: GitHub personal access token
        repo: Repository in format "owner/repo"
        query: Search query (title/body keywords)
        state: Issue state - "open", "closed", or "all" (default: "open")
        max_results: Maximum number of results to return (default: 5)

    Returns:
        dict with search results:
        {
            "repository": str,
            "issues": list[dict],  # [{number, title, state, html_url, created_at, labels}]
            "total_count": int,
            "error": str | None
        }
    """
    try:
        github = get_github_client(token)

        # Build search query
        search_query = f"{query} repo:{repo} is:issue"
        if state != "all":
            search_query += f" state:{state}"

        # Search issues
        result = github.search_issues(query=search_query)

        issues = []
        for idx, issue in enumerate(result):
            if idx >= max_results:
                break

            # Skip pull requests
            if issue.pull_request is not None:
                continue

            issues.append({
                "number": issue.number,
                "title": issue.title,
                "state": issue.state,
                "html_url": issue.html_url,
                "created_at": issue.created_at.isoformat(),
                "labels": [label.name for label in issue.labels]
            })

        return {
            "repository": repo,
            "issues": issues,
            "total_count": result.totalCount,
            "error": None
        }

    except GithubException as e:
        error_msg = format_github_error(e, f"Unable to search issues in repository '{repo}'.")
        return {
            "repository": repo,
            "issues": [],
            "total_count": 0,
            "error": error_msg
        }

    except Exception as e:
        return {
            "repository": repo,
            "issues": [],
            "total_count": 0,
            "error": f"Unexpected error: {str(e)}"
        }


def list_pull_requests(
    token: str,
    repo: str,
    state: str = "open",
    per_page: int = 50,
    page: int = 1,
    skip_cache: bool = False
) -> dict:
    """
    List pull requests from a repository.

    Args:
        token: GitHub personal access token
        repo: Repository in format "owner/repo"
        state: PR state - "open", "closed", or "all" (default: "open")
        per_page: Number of PRs per page (max 100, default 50)
        page: Page number for pagination (default 1)
        skip_cache: If True, bypass cache and fetch fresh data (default: False)

    Returns:
        dict with PR list:
        {
            "repository": str,
            "pull_requests": list[dict],  # [{number, title, state, html_url, head_branch, base_branch, created_at, updated_at, labels, draft, mergeable_state}]
            "total_count": int,
            "has_next": bool,
            "error": str | None
        }
    """
    cache_key = f"prs:{hash(token)}:{repo}:{state}:{page}"

    if not skip_cache:
        cached = _get_from_cache(cache_key)
        if cached:
            return cached

    try:
        github = get_github_client(token)
        repository = github.get_repo(repo)

        # Get pull requests with pagination
        prs_paginated = repository.get_pulls(state=state, sort="updated", direction="desc")

        # Calculate start and end indices for pagination
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page

        # Convert to list and slice for pagination
        all_prs = []
        for idx, pr in enumerate(prs_paginated):
            if idx < start_idx:
                continue
            if idx >= end_idx:
                break

            all_prs.append({
                "number": pr.number,
                "title": pr.title,
                "state": pr.state,
                "html_url": pr.html_url,
                "head_branch": pr.head.ref,
                "base_branch": pr.base.ref,
                "created_at": pr.created_at.isoformat(),
                "updated_at": pr.updated_at.isoformat(),
                "labels": [label.name for label in pr.labels],
                "draft": pr.draft,
                "mergeable_state": pr.mergeable_state or "unknown",
            })

        # Check if there are more pages
        has_next = len(all_prs) == per_page

        result = {
            "repository": repo,
            "pull_requests": all_prs,
            "total_count": len(all_prs),
            "has_next": has_next,
            "error": None
        }

        _set_cache(cache_key, result)
        return result

    except GithubException as e:
        error_msg = format_github_error(e, f"Unable to list pull requests for repository '{repo}'.")
        return {
            "repository": repo,
            "pull_requests": [],
            "total_count": 0,
            "has_next": False,
            "error": error_msg
        }

    except Exception as e:
        return {
            "repository": repo,
            "pull_requests": [],
            "total_count": 0,
            "has_next": False,
            "error": f"Unexpected error: {str(e)}"
        }


def get_pull_request_details(token: str, repo: str, pr_number: int) -> dict:
    """
    Get full details of a pull request including body, reviews, and merge conflicts.

    Args:
        token: GitHub personal access token
        repo: Repository in format "owner/repo"
        pr_number: Pull request number

    Returns:
        dict with PR details:
        {
            "number": int,
            "title": str,
            "body": str | None,
            "state": str,
            "labels": list[str],
            "html_url": str,
            "head_branch": str,
            "base_branch": str,
            "created_at": str,
            "updated_at": str,
            "draft": bool,
            "mergeable": bool | None,
            "mergeable_state": str,
            "has_conflicts": bool,
            "reviews": list[dict],  # [{id, user, state, body, submitted_at}]
            "review_comments": list[dict],  # [{id, user, body, path, line, created_at}]
            "error": str | None
        }
    """
    try:
        github = get_github_client(token)
        repository = github.get_repo(repo)
        pr = repository.get_pull(pr_number)

        # Get reviews
        reviews = []
        for review in pr.get_reviews():
            reviews.append({
                "id": review.id,
                "user": review.user.login if review.user else "unknown",
                "state": review.state,
                "body": review.body or "",
                "submitted_at": review.submitted_at.isoformat() if review.submitted_at else None,
            })

        # Get review comments (inline code comments)
        review_comments = []
        for comment in pr.get_review_comments():
            review_comments.append({
                "id": comment.id,
                "user": comment.user.login if comment.user else "unknown",
                "body": comment.body,
                "path": comment.path,
                "line": comment.line if hasattr(comment, 'line') else None,
                "created_at": comment.created_at.isoformat(),
            })

        # Check for merge conflicts
        has_conflicts = pr.mergeable_state in ["dirty", "blocked"] or pr.mergeable is False

        # Check if PR is from a fork
        is_from_fork = pr.head.repo and pr.base.repo and pr.head.repo.full_name != pr.base.repo.full_name

        return {
            "number": pr.number,
            "title": pr.title,
            "body": pr.body or "",
            "state": pr.state,
            "labels": [label.name for label in pr.labels],
            "html_url": pr.html_url,
            "head_branch": pr.head.ref,
            "base_branch": pr.base.ref,
            "is_from_fork": is_from_fork,
            "head_repo": pr.head.repo.full_name if pr.head.repo else None,
            "created_at": pr.created_at.isoformat(),
            "updated_at": pr.updated_at.isoformat(),
            "draft": pr.draft,
            "mergeable": pr.mergeable,
            "mergeable_state": pr.mergeable_state or "unknown",
            "has_conflicts": has_conflicts,
            "reviews": reviews,
            "review_comments": review_comments,
            "error": None
        }

    except GithubException as e:
        error_msg = format_github_error(e, f"Unable to get details for PR #{pr_number}.")
        return {"error": error_msg}

    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


def find_pr_by_branch(
    token: str,
    repo: str,
    head_branch: str,
    base_branch: str | None = None,
    state: str = "all"
) -> dict:
    """
    Find a pull request by its head branch name.

    This function searches for PRs from the specified head branch, optionally
    filtering by base branch and state. Useful for checking if a PR already
    exists before creating a new one.

    Args:
        token: GitHub personal access token
        repo: Repository in format "owner/repo"
        head_branch: The source branch name (without owner prefix)
        base_branch: Optional target branch to filter by
        state: PR state filter - "open", "closed", or "all" (default: "all")

    Returns:
        dict with result:
        {
            "found": bool,
            "pr": dict | None,  # PR details if found: {number, title, state, html_url, head_branch, base_branch, merged, merged_at, created_at, updated_at}
            "error": str | None
        }
    """
    try:
        github = get_github_client(token)
        repository = github.get_repo(repo)

        # Get PRs filtering by head branch
        # GitHub API expects head in format "owner:branch" for cross-repo PRs
        # or just "branch" for same-repo PRs
        prs = repository.get_pulls(state=state, head=f"{repository.owner.login}:{head_branch}")

        for pr in prs:
            # Optionally filter by base branch
            if base_branch and pr.base.ref != base_branch:
                continue

            return {
                "found": True,
                "pr": {
                    "number": pr.number,
                    "title": pr.title,
                    "state": pr.state,
                    "html_url": pr.html_url,
                    "head_branch": pr.head.ref,
                    "base_branch": pr.base.ref,
                    "merged": pr.merged,
                    "merged_at": pr.merged_at.isoformat() if pr.merged_at else None,
                    "created_at": pr.created_at.isoformat(),
                    "updated_at": pr.updated_at.isoformat(),
                    "draft": pr.draft,
                },
                "error": None
            }

        return {
            "found": False,
            "pr": None,
            "error": None
        }

    except GithubException as e:
        error_msg = format_github_error(e, f"Unable to search for PR with branch '{head_branch}'.")
        return {
            "found": False,
            "pr": None,
            "error": error_msg
        }

    except Exception as e:
        return {
            "found": False,
            "pr": None,
            "error": f"Unexpected error: {str(e)}"
        }


def get_pr_comments(
    token: str,
    repo: str,
    pr_number: int,
    since: str | None = None
) -> dict:
    """
    Get comments (issue comments, not review comments) on a pull request.

    Args:
        token: GitHub personal access token
        repo: Repository in format "owner/repo"
        pr_number: Pull request number
        since: Optional ISO 8601 timestamp to filter comments created after this time

    Returns:
        dict with result:
        {
            "comments": list[dict],  # [{id, user, body, created_at, updated_at}]
            "total_count": int,
            "error": str | None
        }
    """
    try:
        github = get_github_client(token)
        repository = github.get_repo(repo)
        pr = repository.get_pull(pr_number)

        comments = []
        for comment in pr.get_issue_comments():
            # Filter by since timestamp if provided
            if since:
                from datetime import datetime
                since_dt = datetime.fromisoformat(since.replace('Z', '+00:00'))
                if comment.created_at < since_dt:
                    continue

            comments.append({
                "id": comment.id,
                "user": comment.user.login if comment.user else "unknown",
                "body": comment.body,
                "created_at": comment.created_at.isoformat(),
                "updated_at": comment.updated_at.isoformat() if comment.updated_at else None,
            })

        return {
            "comments": comments,
            "total_count": len(comments),
            "error": None
        }

    except GithubException as e:
        error_msg = format_github_error(e, f"Unable to get comments for PR #{pr_number}.")
        return {
            "comments": [],
            "total_count": 0,
            "error": error_msg
        }

    except Exception as e:
        return {
            "comments": [],
            "total_count": 0,
            "error": f"Unexpected error: {str(e)}"
        }


def get_github_token_for_workspace(workspace_id: int, db) -> str | None:
    """
    Get a GitHub token for a workspace from the workspace owner.

    This function retrieves the encrypted GitHub token from the workspace owner
    and decrypts it for use in API calls.

    Args:
        workspace_id: Workspace ID
        db: Database session

    Returns:
        Decrypted GitHub token, or None if not available
    """
    from app.models.workspace import Workspace
    from app.services.encryption_service import decrypt_token

    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()

    if not workspace:
        return None

    # Try workspace owner's token first
    if workspace.owner and workspace.owner.github_token_encrypted:
        try:
            return decrypt_token(workspace.owner.github_token_encrypted)
        except Exception:
            pass

    # Fallback: Try to find any admin member with a token
    from app.models.workspace_member import WorkspaceMember
    from app.models.user import User

    admin_member = db.query(WorkspaceMember).join(User).filter(
        WorkspaceMember.workspace_id == workspace_id,
        WorkspaceMember.role == "admin",
        User.github_token_encrypted.isnot(None)
    ).first()

    if admin_member and admin_member.user.github_token_encrypted:
        try:
            return decrypt_token(admin_member.user.github_token_encrypted)
        except Exception:
            pass

    return None


def get_issue_blocked_by(token: str, repo: str, issue_number: int) -> dict:
    """
    Check if a GitHub issue has active "blocked by" relationships.

    Uses the GitHub REST API issue dependencies endpoint:
    GET /repos/{owner}/{repo}/issues/{issue_number}/dependencies/blocked_by

    Args:
        token: GitHub personal access token
        repo: Repository in format "owner/repo"
        issue_number: Issue number to check

    Returns:
        dict with blocking info:
        {
            "is_blocked": bool,
            "open_blockers": list[dict],  # [{repo, number, title, state}]
            "error": str | None
        }
    """
    url = f"https://api.github.com/repos/{repo}/issues/{issue_number}/dependencies/blocked_by"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    try:
        response = httpx.get(url, headers=headers, timeout=30.0)

        if response.status_code == 404:
            # No dependencies endpoint or issue not found - treat as not blocked
            return {"is_blocked": False, "open_blockers": [], "error": None}

        response.raise_for_status()
        blockers = response.json()

        if not isinstance(blockers, list):
            return {"is_blocked": False, "open_blockers": [], "error": None}

        open_blockers = []
        for blocker in blockers:
            blocker_state = blocker.get("state", "")
            if blocker_state == "open":
                blocker_repo = blocker.get("repository", {}).get("full_name", repo)
                open_blockers.append({
                    "repo": blocker_repo,
                    "number": blocker.get("number"),
                    "title": blocker.get("title", ""),
                    "state": blocker_state,
                })

        return {
            "is_blocked": len(open_blockers) > 0,
            "open_blockers": open_blockers,
            "error": None,
        }

    except httpx.HTTPStatusError as e:
        return {
            "is_blocked": False,
            "open_blockers": [],
            "error": f"GitHub API error (status {e.response.status_code}): {str(e)}",
        }
    except httpx.RequestError as e:
        return {
            "is_blocked": False,
            "open_blockers": [],
            "error": f"GitHub API request failed: {str(e)}",
        }
    except Exception as e:
        return {
            "is_blocked": False,
            "open_blockers": [],
            "error": f"Unexpected error checking blocked-by: {str(e)}",
        }
