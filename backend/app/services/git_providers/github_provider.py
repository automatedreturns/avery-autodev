"""GitHub provider implementation using existing github_service."""

import re
from typing import Any

from app.services.git_providers.base import GitProvider, GitProviderType
from app.services import github_service
from app.services.github_actions_service import GitHubActionsService


class GitHubProvider(GitProvider):
    """GitHub implementation of the GitProvider interface.

    Delegates to the existing github_service module functions and
    GitHubActionsService for CI operations.
    """

    provider_type = GitProviderType.GITHUB

    def get_username(self, token: str) -> str | None:
        return github_service.get_github_username(token)

    # ── Repository operations ──────────────────────────────────────────

    def validate_repository(self, token: str, repo: str) -> dict[str, Any]:
        return github_service.validate_repository(token, repo)

    def list_branches(self, token: str, repo: str, skip_cache: bool = False) -> dict[str, Any]:
        return github_service.list_branches(token, repo, skip_cache=skip_cache)

    def validate_branch(self, token: str, repo: str, branch: str) -> bool:
        return github_service.validate_branch(token, repo, branch)

    def get_repository_tree(
        self, token: str, repo: str, branch: str, path: str = ""
    ) -> dict[str, Any]:
        return github_service.get_repository_tree(token, repo, branch, path)

    # ── Issue operations ───────────────────────────────────────────────

    def list_issues(
        self,
        token: str,
        repo: str,
        state: str = "open",
        per_page: int = 30,
        page: int = 1,
        skip_cache: bool = False,
    ) -> dict[str, Any]:
        return github_service.list_issues(
            token, repo, state=state, per_page=per_page, page=page, skip_cache=skip_cache
        )

    def get_issue_details(self, token: str, repo: str, issue_number: int) -> dict[str, Any]:
        return github_service.get_issue_details(token, repo, issue_number)

    def validate_issue_exists(self, token: str, repo: str, issue_number: int) -> dict[str, Any]:
        return github_service.validate_issue_exists(token, repo, issue_number)

    def create_issue(
        self,
        token: str,
        repo: str,
        title: str,
        body: str,
        labels: list[str] | None = None,
        assignees: list[str] | None = None,
    ) -> dict[str, Any]:
        return github_service.create_issue(token, repo, title, body, labels=labels, assignees=assignees)

    def search_similar_issues(
        self, token: str, repo: str, keywords: list[str]
    ) -> dict[str, Any]:
        query = " ".join(keywords)
        return github_service.search_similar_issues(token, repo, query)

    def get_issue_blocked_by(
        self, token: str, repo: str, issue_number: int
    ) -> dict[str, Any]:
        return github_service.get_issue_blocked_by(token, repo, issue_number)

    # ── Pull Request operations ────────────────────────────────────────

    def list_pull_requests(
        self,
        token: str,
        repo: str,
        state: str = "open",
        per_page: int = 30,
        page: int = 1,
        skip_cache: bool = False,
    ) -> dict[str, Any]:
        return github_service.list_pull_requests(
            token, repo, state=state, per_page=per_page, page=page, skip_cache=skip_cache
        )

    def get_pull_request_details(
        self, token: str, repo: str, pr_number: int
    ) -> dict[str, Any]:
        return github_service.get_pull_request_details(token, repo, pr_number)

    def find_pr_by_branch(self, token: str, repo: str, head_branch: str, base_branch: str | None = None, state: str = "all") -> dict[str, Any]:
        return github_service.find_pr_by_branch(token, repo, head_branch, base_branch, state)

    def get_pr_comments(self, token: str, repo: str, pr_number: int) -> dict[str, Any]:
        return github_service.get_pr_comments(token, repo, pr_number)

    def create_pull_request(
        self,
        token: str,
        repo: str,
        head: str,
        base: str,
        title: str,
        body: str,
        draft: bool = True,
        assignees: list[str] | None = None,
    ) -> dict[str, Any]:
        return github_service.create_pull_request(
            token, repo, head=head, base=base, title=title, body=body,
            draft=draft, assignees=assignees,
        )

    def add_pr_comment(
        self, token: str, repo: str, pr_number: int, body: str
    ) -> dict[str, Any]:
        return github_service.add_pr_comment(token, repo, pr_number, body)

    # ── File / Content operations ──────────────────────────────────────

    def get_file_content(
        self, token: str, repo: str, branch: str, file_path: str
    ) -> dict[str, Any]:
        return github_service.get_file_content(token, repo, branch, file_path)

    def create_or_update_file(
        self,
        token: str,
        repo: str,
        branch: str,
        file_path: str,
        content: str,
        message: str,
        sha: str | None = None,
    ) -> dict[str, Any]:
        return github_service.create_or_update_file(
            token, repo, branch, file_path, content, message, sha=sha
        )

    # ── Branch operations ──────────────────────────────────────────────

    def create_branch(
        self, token: str, repo: str, branch_name: str, base_branch: str
    ) -> dict[str, Any]:
        return github_service.create_branch(token, repo, branch_name, base_branch)

    # ── CI / Pipeline operations ───────────────────────────────────────

    def get_ci_run_status(self, token: str, repo: str, run_id: str) -> dict[str, Any]:
        service = GitHubActionsService(token)
        return service.get_workflow_run_status(repo, run_id)

    def get_ci_run_logs(
        self, token: str, repo: str, run_id: str, job_name: str | None = None
    ) -> str | None:
        service = GitHubActionsService(token)
        return service.get_job_logs(repo, run_id, job_name)

    def get_check_runs_for_pr(self, token: str, repo: str, pr_number: int) -> list[dict]:
        service = GitHubActionsService(token)
        return service.get_check_runs_for_pr(repo, pr_number)

    # ── URL helpers ────────────────────────────────────────────────────

    def normalize_repository(self, input_str: str) -> str | None:
        if not input_str:
            return None

        trimmed = input_str.strip()

        # Short format: owner/repo
        if re.match(r'^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$', trimmed):
            return trimmed

        # HTTPS URL: https://github.com/owner/repo
        https_match = re.match(
            r'^https?://github\.com/([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+?)(\.git)?$',
            trimmed
        )
        if https_match:
            return f"{https_match.group(1)}/{https_match.group(2)}"

        # SSH URL: git@github.com:owner/repo.git
        ssh_match = re.match(
            r'^git@github\.com:([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+?)(\.git)?$',
            trimmed
        )
        if ssh_match:
            return f"{ssh_match.group(1)}/{ssh_match.group(2)}"

        return None

    def get_clone_url(self, repo: str, token: str) -> str:
        return f"https://x-access-token:{token}@github.com/{repo}.git"

    def get_repo_web_url(self, repo: str) -> str:
        return f"https://github.com/{repo}"
