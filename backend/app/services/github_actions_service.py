"""GitHub Actions API integration service for CI/CD operations."""

import logging
import re
from typing import Optional

from github import Github, GithubException
from github.WorkflowRun import WorkflowRun
from github.CheckRun import CheckRun

from app.services.github_service import get_github_client, format_github_error

logger = logging.getLogger(__name__)


class GitHubActionsError(Exception):
    """Custom exception for GitHub Actions operations."""
    pass


class GitHubActionsService:
    """Service for interacting with GitHub Actions API."""

    def __init__(self, github_token: str):
        """
        Initialize GitHub Actions service.

        Args:
            github_token: GitHub personal access token with workflow permissions
        """
        self.client: Github = get_github_client(github_token)
        self.token = github_token

    def get_workflow_run(self, repo_name: str, run_id: str) -> Optional[WorkflowRun]:
        """
        Get workflow run details from GitHub Actions.

        Args:
            repo_name: Repository name in format "owner/repo"
            run_id: GitHub Actions run ID

        Returns:
            WorkflowRun object or None if not found

        Raises:
            GitHubActionsError: If API call fails
        """
        try:
            repo = self.client.get_repo(repo_name)
            run = repo.get_workflow_run(int(run_id))
            return run
        except GithubException as e:
            error_msg = format_github_error(e, f"Failed to get workflow run {run_id}")
            logger.error(error_msg)
            raise GitHubActionsError(error_msg) from e
        except ValueError as e:
            error_msg = f"Invalid run_id format: {run_id}. Must be a valid integer."
            logger.error(error_msg)
            raise GitHubActionsError(error_msg) from e
        except Exception as e:
            logger.error(f"Unexpected error getting workflow run: {e}")
            return None

    def get_workflow_run_status(self, repo_name: str, run_id: str) -> dict:
        """
        Get workflow run status and conclusion.

        Args:
            repo_name: Repository name in format "owner/repo"
            run_id: GitHub Actions run ID

        Returns:
            Dictionary with status, conclusion, and timestamps
        """
        run = self.get_workflow_run(repo_name, run_id)
        if not run:
            return {
                "status": "unknown",
                "conclusion": None,
                "started_at": None,
                "completed_at": None,
                "logs_url": None
            }

        return {
            "status": run.status,
            "conclusion": run.conclusion,
            "started_at": run.created_at,
            "completed_at": run.updated_at,
            "logs_url": run.logs_url,
            "html_url": run.html_url
        }

    def download_workflow_logs(self, repo_name: str, run_id: str) -> Optional[str]:
        """
        Get workflow logs URL (GitHub returns logs as a zip file).

        Args:
            repo_name: Repository name in format "owner/repo"
            run_id: GitHub Actions run ID

        Returns:
            Logs URL or None if unavailable
        """
        run = self.get_workflow_run(repo_name, run_id)
        if not run:
            return None

        try:
            # Note: GitHub API returns logs as a zip file download URL
            # For actual log parsing, we'd need to download and extract
            return run.logs_url
        except Exception as e:
            logger.error(f"Failed to get logs URL: {e}")
            return None

    def get_job_logs(self, repo_name: str, run_id: str, job_name: Optional[str] = None) -> Optional[str]:
        """
        Download and extract job logs from GitHub Actions.

        Args:
            repo_name: Repository name in format "owner/repo"
            run_id: GitHub Actions run ID
            job_name: Specific job name to get logs for (optional)

        Returns:
            Raw log text or None if unavailable
        """
        import requests
        import zipfile
        import io

        try:
            run = self.get_workflow_run(repo_name, run_id)
            if not run:
                return None

            # Get logs URL - requires authentication
            logs_url = run.logs_url
            if not logs_url:
                logger.warning(f"No logs URL available for run {run_id}")
                return None

            # Download logs zip file
            headers = {
                "Authorization": f"token {self.token}",
                "Accept": "application/vnd.github.v3+json"
            }

            response = requests.get(logs_url, headers=headers, timeout=30)
            response.raise_for_status()

            # Extract logs from zip
            log_content = []
            with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
                # If job_name specified, only extract that job's log
                if job_name:
                    # Find matching log file
                    matching_files = [f for f in zip_file.namelist() if job_name.lower() in f.lower()]
                    for file_name in matching_files:
                        with zip_file.open(file_name) as log_file:
                            log_content.append(log_file.read().decode('utf-8', errors='ignore'))
                else:
                    # Extract all log files
                    for file_name in zip_file.namelist():
                        if file_name.endswith('.txt'):
                            with zip_file.open(file_name) as log_file:
                                log_content.append(f"\n=== {file_name} ===\n")
                                log_content.append(log_file.read().decode('utf-8', errors='ignore'))

            combined_logs = "\n".join(log_content)
            logger.info(f"Downloaded {len(combined_logs)} characters of logs for run {run_id}")
            return combined_logs

        except requests.RequestException as e:
            logger.error(f"Failed to download logs for run {run_id}: {e}")
            return None
        except zipfile.BadZipFile as e:
            logger.error(f"Invalid zip file for logs: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error downloading job logs: {e}", exc_info=True)
            return None

    def parse_workflow_logs(self, logs: str) -> dict:
        """
        Parse workflow logs to extract structured error information.

        Args:
            logs: Raw log text from workflow execution

        Returns:
            Dictionary with categorized errors
        """
        errors = {
            "test_failures": [],
            "lint_errors": [],
            "type_errors": [],
            "build_errors": [],
            "import_errors": [],
            "syntax_errors": []
        }

        if not logs:
            return errors

        lines = logs.split("\n")

        for i, line in enumerate(lines):
            # Parse pytest failures
            if "FAILED" in line and "::" in line:
                errors["test_failures"].append({
                    "line": line.strip(),
                    "context": self._get_context(lines, i, 2)
                })

            # Parse ruff/flake8 lint errors
            if re.search(r'\.(py|js|ts|tsx):\d+:\d+:', line) and ("error:" in line.lower() or "E[0-9]" in line):
                errors["lint_errors"].append({
                    "line": line.strip(),
                    "context": self._get_context(lines, i, 1)
                })

            # Parse mypy type errors
            if "error:" in line.lower() and ".py:" in line:
                errors["type_errors"].append({
                    "line": line.strip(),
                    "context": self._get_context(lines, i, 1)
                })

            # Parse build errors
            if "error:" in line.lower() and ("build" in line.lower() or "compilation" in line.lower()):
                errors["build_errors"].append({
                    "line": line.strip(),
                    "context": self._get_context(lines, i, 2)
                })

            # Parse import errors
            if "ImportError" in line or "ModuleNotFoundError" in line:
                errors["import_errors"].append({
                    "line": line.strip(),
                    "context": self._get_context(lines, i, 2)
                })

            # Parse syntax errors
            if "SyntaxError" in line:
                errors["syntax_errors"].append({
                    "line": line.strip(),
                    "context": self._get_context(lines, i, 3)
                })

        return errors

    def _get_context(self, lines: list[str], index: int, context_lines: int = 2) -> list[str]:
        """
        Get context lines around a specific line index.

        Args:
            lines: All log lines
            index: Index of the target line
            context_lines: Number of lines to include before and after

        Returns:
            List of context lines
        """
        start = max(0, index - context_lines)
        end = min(len(lines), index + context_lines + 1)
        return [line.strip() for line in lines[start:end] if line.strip()]

    def get_check_runs_for_pr(self, repo_name: str, pr_number: int) -> list[dict]:
        """
        Get all check runs for a pull request.

        Args:
            repo_name: Repository name in format "owner/repo"
            pr_number: Pull request number

        Returns:
            List of check run summaries
        """
        try:
            repo = self.client.get_repo(repo_name)
            pr = repo.get_pull(pr_number)

            # Get the latest commit
            commits = list(pr.get_commits())
            if not commits:
                logger.warning(f"No commits found for PR #{pr_number}")
                return []

            latest_commit = commits[-1]

            # Get check runs for the commit
            check_runs = latest_commit.get_check_runs()

            return [
                {
                    "id": run.id,
                    "name": run.name,
                    "status": run.status,
                    "conclusion": run.conclusion,
                    "started_at": run.started_at,
                    "completed_at": run.completed_at,
                    "details_url": run.details_url,
                    "output_title": run.output.get("title") if run.output else None,
                    "output_summary": run.output.get("summary") if run.output else None
                }
                for run in check_runs
            ]
        except GithubException as e:
            error_msg = format_github_error(e, f"Failed to get check runs for PR #{pr_number}")
            logger.error(error_msg)
            return []
        except Exception as e:
            logger.error(f"Unexpected error getting check runs: {e}")
            return []

    def wait_for_checks_completion(self, repo_name: str, pr_number: int, timeout_seconds: int = 600) -> dict:
        """
        Wait for all checks on a PR to complete (with timeout).

        Args:
            repo_name: Repository name in format "owner/repo"
            pr_number: Pull request number
            timeout_seconds: Maximum time to wait in seconds (default: 10 minutes)

        Returns:
            Dictionary with completion status and check results
        """
        import time

        start_time = time.time()
        check_interval = 30  # Check every 30 seconds

        while time.time() - start_time < timeout_seconds:
            check_runs = self.get_check_runs_for_pr(repo_name, pr_number)

            if not check_runs:
                logger.warning(f"No check runs found for PR #{pr_number}")
                time.sleep(check_interval)
                continue

            # Check if all runs are completed
            all_completed = all(
                run["status"] == "completed"
                for run in check_runs
            )

            if all_completed:
                all_passed = all(
                    run["conclusion"] == "success"
                    for run in check_runs
                )

                return {
                    "completed": True,
                    "all_passed": all_passed,
                    "check_runs": check_runs,
                    "duration_seconds": time.time() - start_time
                }

            # Wait before checking again
            time.sleep(check_interval)

        # Timeout reached
        return {
            "completed": False,
            "all_passed": False,
            "check_runs": self.get_check_runs_for_pr(repo_name, pr_number),
            "duration_seconds": timeout_seconds,
            "timeout": True
        }

    def create_error_summary(self, parsed_errors: dict) -> str:
        """
        Create a human-readable error summary from parsed errors.

        Args:
            parsed_errors: Dictionary of categorized errors from parse_workflow_logs

        Returns:
            Human-readable error summary
        """
        summary_parts = []

        if parsed_errors["test_failures"]:
            count = len(parsed_errors["test_failures"])
            summary_parts.append(f"❌ {count} test(s) failed")
            # Add first few failures as examples
            for failure in parsed_errors["test_failures"][:3]:
                summary_parts.append(f"  • {failure['line']}")

        if parsed_errors["lint_errors"]:
            count = len(parsed_errors["lint_errors"])
            summary_parts.append(f"⚠️  {count} lint error(s)")
            for error in parsed_errors["lint_errors"][:3]:
                summary_parts.append(f"  • {error['line']}")

        if parsed_errors["type_errors"]:
            count = len(parsed_errors["type_errors"])
            summary_parts.append(f"🔍 {count} type error(s)")
            for error in parsed_errors["type_errors"][:3]:
                summary_parts.append(f"  • {error['line']}")

        if parsed_errors["import_errors"]:
            count = len(parsed_errors["import_errors"])
            summary_parts.append(f"📦 {count} import error(s)")
            for error in parsed_errors["import_errors"][:3]:
                summary_parts.append(f"  • {error['line']}")

        if parsed_errors["syntax_errors"]:
            count = len(parsed_errors["syntax_errors"])
            summary_parts.append(f"💥 {count} syntax error(s)")
            for error in parsed_errors["syntax_errors"][:3]:
                summary_parts.append(f"  • {error['line']}")

        if parsed_errors["build_errors"]:
            count = len(parsed_errors["build_errors"])
            summary_parts.append(f"🔨 {count} build error(s)")
            for error in parsed_errors["build_errors"][:3]:
                summary_parts.append(f"  • {error['line']}")

        if not summary_parts:
            return "No specific errors identified in logs."

        return "\n".join(summary_parts)
