"""Abstract base class for Git hosting provider integrations."""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any


class GitProviderType(str, Enum):
    """Supported git hosting providers."""
    GITHUB = "github"
    GITLAB = "gitlab"


class GitProvider(ABC):
    """
    Abstract base class defining the interface for git hosting provider integrations.

    All provider implementations (GitHub, GitLab, etc.) must implement these methods
    to provide a consistent API for the rest of the application.
    """

    provider_type: GitProviderType

    @abstractmethod
    def get_username(self, token: str) -> str | None:
        """Get the authenticated user's username."""
        ...

    # ── Repository operations ──────────────────────────────────────────

    @abstractmethod
    def validate_repository(self, token: str, repo: str) -> dict[str, Any]:
        """
        Validate that a repository exists and the user has access.

        Returns:
            dict with keys: valid (bool), repository, description, default_branch, error
        """
        ...

    @abstractmethod
    def list_branches(self, token: str, repo: str, skip_cache: bool = False) -> dict[str, Any]:
        """
        List all branches for a repository.

        Returns:
            dict with keys: repository, branches (list[str]), error
        """
        ...

    @abstractmethod
    def validate_branch(self, token: str, repo: str, branch: str) -> bool:
        """Check if a branch exists in the repository."""
        ...

    @abstractmethod
    def get_repository_tree(
        self, token: str, repo: str, branch: str, path: str = ""
    ) -> dict[str, Any]:
        """
        Get the file tree structure of a repository.

        Returns:
            dict with keys: tree (list of file info dicts), error
        """
        ...

    # ── Issue operations ───────────────────────────────────────────────

    @abstractmethod
    def list_issues(
        self,
        token: str,
        repo: str,
        state: str = "open",
        per_page: int = 30,
        page: int = 1,
        skip_cache: bool = False,
    ) -> dict[str, Any]:
        """
        List issues in a repository.

        Returns:
            dict with keys: issues (list[dict]), total_count, has_more, error
        """
        ...

    @abstractmethod
    def get_issue_details(self, token: str, repo: str, issue_number: int) -> dict[str, Any]:
        """
        Get detailed information about a specific issue.

        Returns:
            dict with issue details including: number, title, body, state, labels, etc.
        """
        ...

    @abstractmethod
    def validate_issue_exists(self, token: str, repo: str, issue_number: int) -> dict[str, Any]:
        """
        Validate that an issue exists.

        Returns:
            dict with keys: exists (bool), issue (dict | None), error
        """
        ...

    @abstractmethod
    def create_issue(
        self,
        token: str,
        repo: str,
        title: str,
        body: str,
        labels: list[str] | None = None,
        assignees: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Create a new issue.

        Returns:
            dict with keys: number, title, html_url, error
        """
        ...

    @abstractmethod
    def search_similar_issues(
        self, token: str, repo: str, keywords: list[str]
    ) -> dict[str, Any]:
        """
        Search for similar issues by keywords.

        Returns:
            dict with keys: issues (list[dict]), error
        """
        ...

    @abstractmethod
    def get_issue_blocked_by(
        self, token: str, repo: str, issue_number: int
    ) -> dict[str, Any]:
        """
        Check if an issue is blocked by other issues.

        Returns:
            dict with keys: is_blocked (bool), open_blockers (list), error
        """
        ...

    # ── Pull / Merge Request operations ────────────────────────────────

    @abstractmethod
    def list_pull_requests(
        self,
        token: str,
        repo: str,
        state: str = "open",
        per_page: int = 30,
        page: int = 1,
        skip_cache: bool = False,
    ) -> dict[str, Any]:
        """
        List pull/merge requests.

        Returns:
            dict with keys: pull_requests (list[dict]), total_count, has_more, error
        """
        ...

    @abstractmethod
    def get_pull_request_details(
        self, token: str, repo: str, pr_number: int
    ) -> dict[str, Any]:
        """
        Get detailed information about a pull/merge request.

        Returns:
            dict with PR details including: number, title, body, state, head_branch, base_branch, etc.
        """
        ...

    @abstractmethod
    def find_pr_by_branch(self, token: str, repo: str, head_branch: str, base_branch: str | None = None, state: str = "all") -> dict[str, Any]:
        """
        Find a pull/merge request by its head branch name.

        Args:
            token: Auth token
            repo: Repository path
            head_branch: Source branch name
            base_branch: Target branch name (optional filter)
            state: PR state filter ("open", "closed", "all")

        Returns:
            dict with PR details or error
        """
        ...

    @abstractmethod
    def get_pr_comments(self, token: str, repo: str, pr_number: int) -> dict[str, Any]:
        """
        Get comments on a pull/merge request.

        Returns:
            dict with keys: comments (list[dict]), error
        """
        ...

    @abstractmethod
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
        """
        Create a pull/merge request.

        Returns:
            dict with keys: success, pr_number, pr_url, error
        """
        ...

    @abstractmethod
    def add_pr_comment(
        self, token: str, repo: str, pr_number: int, body: str
    ) -> dict[str, Any]:
        """
        Add a comment to a pull/merge request.

        Returns:
            dict with keys: id, body, html_url, error
        """
        ...

    # ── File / Content operations ──────────────────────────────────────

    @abstractmethod
    def get_file_content(
        self, token: str, repo: str, branch: str, file_path: str
    ) -> dict[str, Any]:
        """
        Get the content of a file from a repository.

        Returns:
            dict with keys: content (str), sha, encoding, error
        """
        ...

    @abstractmethod
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
        """
        Create or update a file in the repository.

        Returns:
            dict with keys: sha, commit_sha, error
        """
        ...

    # ── Branch operations ──────────────────────────────────────────────

    @abstractmethod
    def create_branch(
        self, token: str, repo: str, branch_name: str, base_branch: str
    ) -> dict[str, Any]:
        """
        Create a new branch.

        Returns:
            dict with keys: name, sha, error
        """
        ...

    # ── CI / Pipeline operations ───────────────────────────────────────

    @abstractmethod
    def get_ci_run_status(self, token: str, repo: str, run_id: str) -> dict[str, Any]:
        """
        Get CI run / pipeline status.

        Returns:
            dict with keys: status, conclusion, started_at, completed_at, logs_url, html_url
        """
        ...

    @abstractmethod
    def get_ci_run_logs(
        self, token: str, repo: str, run_id: str, job_name: str | None = None
    ) -> str | None:
        """
        Download CI run logs.

        Returns:
            Raw log text or None if unavailable
        """
        ...

    @abstractmethod
    def get_check_runs_for_pr(self, token: str, repo: str, pr_number: int) -> list[dict]:
        """
        Get all check/pipeline runs for a pull/merge request.

        Returns:
            List of check run summary dicts
        """
        ...

    # ── URL helpers ────────────────────────────────────────────────────

    @abstractmethod
    def normalize_repository(self, input_str: str) -> str | None:
        """
        Normalize repository input to the canonical owner/repo or namespace/project format.

        Returns:
            Normalized repository string or None if invalid
        """
        ...

    @abstractmethod
    def get_clone_url(self, repo: str, token: str) -> str:
        """
        Get the authenticated clone URL for a repository.

        Returns:
            HTTPS clone URL with embedded token
        """
        ...

    @abstractmethod
    def get_repo_web_url(self, repo: str) -> str:
        """
        Get the web URL for a repository.

        Returns:
            Browser-accessible URL for the repository
        """
        ...
