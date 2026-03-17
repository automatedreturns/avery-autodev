"""GitLab provider implementation using python-gitlab."""

import logging
import re
from typing import Any
from urllib.parse import quote_plus

import httpx

from app.services.git_providers.base import GitProvider, GitProviderType

logger = logging.getLogger(__name__)

# Default GitLab instance URL (can be overridden for self-hosted)
DEFAULT_GITLAB_URL = "https://gitlab.com"


def _gitlab_api(
    token: str,
    method: str,
    path: str,
    gitlab_url: str = DEFAULT_GITLAB_URL,
    **kwargs,
) -> httpx.Response:
    """Make an authenticated GitLab API request."""
    headers = {
        "PRIVATE-TOKEN": token,
        "Content-Type": "application/json",
    }
    url = f"{gitlab_url}/api/v4{path}"
    return httpx.request(method, url, headers=headers, timeout=30.0, **kwargs)


def _project_path(repo: str) -> str:
    """URL-encode a namespace/project path for use in GitLab API URLs."""
    return quote_plus(repo)


def _format_gitlab_error(response: httpx.Response, context: str = "") -> str:
    """Format a GitLab API error into a user-friendly message."""
    status = response.status_code

    if status == 401:
        return "Authentication failed. Your GitLab token may be invalid or expired. Please reconnect your GitLab account."
    elif status == 403:
        return f"Permission denied. Your GitLab token doesn't have sufficient permissions. {context}"
    elif status == 404:
        return f"Not found. {context}"
    elif status == 422:
        try:
            detail = response.json()
            msg = detail.get("message", detail.get("error", str(detail)))
        except Exception:
            msg = response.text
        return f"Validation error: {msg}"
    else:
        try:
            detail = response.json()
            msg = detail.get("message", detail.get("error", str(detail)))
        except Exception:
            msg = response.text
        return f"GitLab API error (status {status}): {msg}"


class GitLabProvider(GitProvider):
    """GitLab implementation of the GitProvider interface.

    Uses the GitLab REST API v4 via httpx for all operations.
    Supports both gitlab.com and self-hosted GitLab instances.
    """

    provider_type = GitProviderType.GITLAB

    def __init__(self, gitlab_url: str = DEFAULT_GITLAB_URL):
        self.gitlab_url = gitlab_url.rstrip("/")

    def _api(self, token: str, method: str, path: str, **kwargs) -> httpx.Response:
        return _gitlab_api(token, method, path, gitlab_url=self.gitlab_url, **kwargs)

    def get_username(self, token: str) -> str | None:
        try:
            resp = self._api(token, "GET", "/user")
            if resp.status_code == 200:
                return resp.json().get("username")
            return None
        except Exception:
            return None

    # ── Repository operations ──────────────────────────────────────────

    def validate_repository(self, token: str, repo: str) -> dict[str, Any]:
        try:
            resp = self._api(token, "GET", f"/projects/{_project_path(repo)}")

            if resp.status_code != 200:
                return {
                    "valid": False,
                    "repository": repo,
                    "description": None,
                    "default_branch": None,
                    "error": _format_gitlab_error(resp, f"Ensure you have access to project '{repo}'."),
                }

            project = resp.json()
            return {
                "valid": True,
                "repository": repo,
                "description": project.get("description"),
                "default_branch": project.get("default_branch"),
                "error": None,
            }
        except Exception as e:
            return {
                "valid": False,
                "repository": repo,
                "description": None,
                "default_branch": None,
                "error": f"Unexpected error: {str(e)}",
            }

    def list_branches(self, token: str, repo: str, skip_cache: bool = False) -> dict[str, Any]:
        try:
            branches = []
            page = 1
            while True:
                resp = self._api(
                    token, "GET",
                    f"/projects/{_project_path(repo)}/repository/branches",
                    params={"per_page": 100, "page": page},
                )
                if resp.status_code != 200:
                    return {
                        "repository": repo,
                        "branches": [],
                        "error": _format_gitlab_error(resp),
                    }

                data = resp.json()
                if not data:
                    break
                branches.extend(b["name"] for b in data)
                if len(data) < 100:
                    break
                page += 1

            return {"repository": repo, "branches": branches, "error": None}
        except Exception as e:
            return {"repository": repo, "branches": [], "error": f"Unexpected error: {str(e)}"}

    def validate_branch(self, token: str, repo: str, branch: str) -> bool:
        try:
            resp = self._api(
                token, "GET",
                f"/projects/{_project_path(repo)}/repository/branches/{quote_plus(branch)}",
            )
            return resp.status_code == 200
        except Exception:
            return False

    def get_repository_tree(
        self, token: str, repo: str, branch: str, path: str = ""
    ) -> dict[str, Any]:
        try:
            tree_items = []
            page = 1
            while True:
                params: dict[str, Any] = {
                    "ref": branch,
                    "recursive": True,
                    "per_page": 100,
                    "page": page,
                }
                if path:
                    params["path"] = path

                resp = self._api(
                    token, "GET",
                    f"/projects/{_project_path(repo)}/repository/tree",
                    params=params,
                )
                if resp.status_code != 200:
                    return {"tree": [], "error": _format_gitlab_error(resp)}

                data = resp.json()
                if not data:
                    break
                for item in data:
                    tree_items.append({
                        "path": item["path"],
                        "type": "blob" if item["type"] == "blob" else "tree",
                        "size": None,  # GitLab tree API doesn't return size
                        "sha": item.get("id"),
                    })
                if len(data) < 100:
                    break
                page += 1

            return {"tree": tree_items, "error": None}
        except Exception as e:
            return {"tree": [], "error": f"Unexpected error: {str(e)}"}

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
        try:
            # Map state: GitLab uses "opened" instead of "open"
            gl_state = "opened" if state == "open" else state

            resp = self._api(
                token, "GET",
                f"/projects/{_project_path(repo)}/issues",
                params={"state": gl_state, "per_page": per_page, "page": page},
            )

            if resp.status_code != 200:
                return {
                    "repository": repo,
                    "issues": [],
                    "total_count": 0,
                    "has_next": False,
                    "error": _format_gitlab_error(resp),
                }

            data = resp.json()
            total = int(resp.headers.get("x-total", len(data)))

            issues = []
            for issue in data:
                issues.append({
                    "number": issue["iid"],  # GitLab uses iid (internal ID)
                    "title": issue["title"],
                    "state": "open" if issue["state"] == "opened" else issue["state"],
                    "html_url": issue["web_url"],
                    "created_at": issue["created_at"],
                    "updated_at": issue["updated_at"],
                    "labels": issue.get("labels", []),
                })

            return {
                "repository": repo,
                "issues": issues,
                "total_count": total,
                "has_next": len(data) == per_page,
                "error": None,
            }
        except Exception as e:
            return {
                "repository": repo,
                "issues": [],
                "total_count": 0,
                "has_next": False,
                "error": f"Unexpected error: {str(e)}",
            }

    def get_issue_details(self, token: str, repo: str, issue_number: int) -> dict[str, Any]:
        try:
            resp = self._api(
                token, "GET",
                f"/projects/{_project_path(repo)}/issues/{issue_number}",
            )

            if resp.status_code != 200:
                return {"error": _format_gitlab_error(resp)}

            issue = resp.json()
            return {
                "number": issue["iid"],
                "title": issue["title"],
                "body": issue.get("description") or "",
                "state": "open" if issue["state"] == "opened" else issue["state"],
                "labels": issue.get("labels", []),
                "html_url": issue["web_url"],
                "created_at": issue["created_at"],
                "updated_at": issue["updated_at"],
                "error": None,
            }
        except Exception as e:
            return {"error": f"Unexpected error: {str(e)}"}

    def validate_issue_exists(self, token: str, repo: str, issue_number: int) -> dict[str, Any]:
        try:
            resp = self._api(
                token, "GET",
                f"/projects/{_project_path(repo)}/issues/{issue_number}",
            )

            if resp.status_code != 200:
                return {
                    "exists": False,
                    "issue_number": issue_number,
                    "issue_url": None,
                    "issue_title": None,
                    "error": _format_gitlab_error(resp),
                }

            issue = resp.json()
            return {
                "exists": True,
                "issue_number": issue["iid"],
                "issue_url": issue["web_url"],
                "issue_title": issue["title"],
                "error": None,
            }
        except Exception as e:
            return {
                "exists": False,
                "issue_number": issue_number,
                "issue_url": None,
                "issue_title": None,
                "error": f"Unexpected error: {str(e)}",
            }

    def create_issue(
        self,
        token: str,
        repo: str,
        title: str,
        body: str,
        labels: list[str] | None = None,
        assignees: list[str] | None = None,
    ) -> dict[str, Any]:
        try:
            payload: dict[str, Any] = {"title": title, "description": body}
            if labels:
                payload["labels"] = ",".join(labels)

            # GitLab uses assignee_ids, so we need to resolve usernames
            # For now, skip assignees as it requires additional API calls
            resp = self._api(
                token, "POST",
                f"/projects/{_project_path(repo)}/issues",
                json=payload,
            )

            if resp.status_code not in (200, 201):
                return {
                    "success": False,
                    "issue_number": None,
                    "issue_url": None,
                    "error": _format_gitlab_error(resp),
                }

            issue = resp.json()
            return {
                "success": True,
                "issue_number": issue["iid"],
                "issue_url": issue["web_url"],
                "error": None,
            }
        except Exception as e:
            return {
                "success": False,
                "issue_number": None,
                "issue_url": None,
                "error": f"Unexpected error: {str(e)}",
            }

    def search_similar_issues(
        self, token: str, repo: str, keywords: list[str]
    ) -> dict[str, Any]:
        try:
            query = " ".join(keywords)
            resp = self._api(
                token, "GET",
                f"/projects/{_project_path(repo)}/issues",
                params={"search": query, "state": "opened", "per_page": 5},
            )

            if resp.status_code != 200:
                return {"repository": repo, "issues": [], "total_count": 0, "error": _format_gitlab_error(resp)}

            data = resp.json()
            issues = []
            for issue in data:
                issues.append({
                    "number": issue["iid"],
                    "title": issue["title"],
                    "state": "open" if issue["state"] == "opened" else issue["state"],
                    "html_url": issue["web_url"],
                    "created_at": issue["created_at"],
                    "labels": issue.get("labels", []),
                })

            return {
                "repository": repo,
                "issues": issues,
                "total_count": len(issues),
                "error": None,
            }
        except Exception as e:
            return {"repository": repo, "issues": [], "total_count": 0, "error": f"Unexpected error: {str(e)}"}

    def get_issue_blocked_by(
        self, token: str, repo: str, issue_number: int
    ) -> dict[str, Any]:
        """GitLab doesn't have a built-in blocked-by API like GitHub.

        We check issue links for 'is_blocked_by' relation type.
        """
        try:
            resp = self._api(
                token, "GET",
                f"/projects/{_project_path(repo)}/issues/{issue_number}/links",
            )

            if resp.status_code == 404:
                return {"is_blocked": False, "open_blockers": [], "error": None}

            if resp.status_code != 200:
                return {"is_blocked": False, "open_blockers": [], "error": _format_gitlab_error(resp)}

            links = resp.json()
            open_blockers = []
            for link in links:
                link_type = link.get("link_type", "")
                if link_type == "is_blocked_by" and link.get("state") == "opened":
                    refs = link.get("references", {})
                    open_blockers.append({
                        "repo": refs.get("full", repo),
                        "number": link.get("iid"),
                        "title": link.get("title", ""),
                        "state": "open",
                    })

            return {
                "is_blocked": len(open_blockers) > 0,
                "open_blockers": open_blockers,
                "error": None,
            }
        except Exception as e:
            return {
                "is_blocked": False,
                "open_blockers": [],
                "error": f"Unexpected error checking blocked-by: {str(e)}",
            }

    # ── Merge Request operations ───────────────────────────────────────

    def list_pull_requests(
        self,
        token: str,
        repo: str,
        state: str = "open",
        per_page: int = 30,
        page: int = 1,
        skip_cache: bool = False,
    ) -> dict[str, Any]:
        try:
            # Map state: GitLab uses "opened"/"merged"/"closed"
            gl_state = "opened" if state == "open" else state

            resp = self._api(
                token, "GET",
                f"/projects/{_project_path(repo)}/merge_requests",
                params={
                    "state": gl_state,
                    "per_page": per_page,
                    "page": page,
                    "order_by": "updated_at",
                    "sort": "desc",
                },
            )

            if resp.status_code != 200:
                return {
                    "repository": repo,
                    "pull_requests": [],
                    "total_count": 0,
                    "has_next": False,
                    "error": _format_gitlab_error(resp),
                }

            data = resp.json()
            prs = []
            for mr in data:
                has_conflicts = mr.get("has_conflicts", False)
                prs.append({
                    "number": mr["iid"],
                    "title": mr["title"],
                    "state": "open" if mr["state"] == "opened" else mr["state"],
                    "html_url": mr["web_url"],
                    "head_branch": mr["source_branch"],
                    "base_branch": mr["target_branch"],
                    "created_at": mr["created_at"],
                    "updated_at": mr["updated_at"],
                    "labels": mr.get("labels", []),
                    "draft": mr.get("draft", False) or mr.get("work_in_progress", False),
                    "mergeable_state": "dirty" if has_conflicts else "clean",
                })

            return {
                "repository": repo,
                "pull_requests": prs,
                "total_count": len(prs),
                "has_next": len(data) == per_page,
                "error": None,
            }
        except Exception as e:
            return {
                "repository": repo,
                "pull_requests": [],
                "total_count": 0,
                "has_next": False,
                "error": f"Unexpected error: {str(e)}",
            }

    def get_pull_request_details(
        self, token: str, repo: str, pr_number: int
    ) -> dict[str, Any]:
        try:
            resp = self._api(
                token, "GET",
                f"/projects/{_project_path(repo)}/merge_requests/{pr_number}",
            )

            if resp.status_code != 200:
                return {"error": _format_gitlab_error(resp)}

            mr = resp.json()
            has_conflicts = mr.get("has_conflicts", False)

            return {
                "number": mr["iid"],
                "title": mr["title"],
                "body": mr.get("description") or "",
                "state": "open" if mr["state"] == "opened" else mr["state"],
                "labels": mr.get("labels", []),
                "html_url": mr["web_url"],
                "head_branch": mr["source_branch"],
                "base_branch": mr["target_branch"],
                "is_from_fork": mr.get("source_project_id") != mr.get("target_project_id"),
                "head_repo": None,  # GitLab handles this differently
                "created_at": mr["created_at"],
                "updated_at": mr["updated_at"],
                "draft": mr.get("draft", False) or mr.get("work_in_progress", False),
                "mergeable": mr.get("merge_status") in ("can_be_merged", "ci_must_pass"),
                "mergeable_state": mr.get("merge_status", "unknown"),
                "has_conflicts": has_conflicts,
                "reviews": [],  # GitLab approvals handled separately
                "review_comments": [],
                "error": None,
            }
        except Exception as e:
            return {"error": f"Unexpected error: {str(e)}"}

    def find_pr_by_branch(self, token: str, repo: str, head_branch: str, base_branch: str | None = None, state: str = "all") -> dict[str, Any]:
        try:
            params: dict[str, Any] = {"source_branch": head_branch, "per_page": 1}
            if base_branch:
                params["target_branch"] = base_branch
            if state and state != "all":
                params["state"] = "opened" if state == "open" else state
            resp = self._api(
                token, "GET",
                f"/projects/{_project_path(repo)}/merge_requests",
                params=params,
            )

            if resp.status_code != 200:
                return {"found": False, "pr": None, "error": _format_gitlab_error(resp)}

            data = resp.json()
            if not data:
                return {"found": False, "pr": None, "error": None}

            mr = data[0]
            return {
                "found": True,
                "pr": {
                    "number": mr["iid"],
                    "title": mr["title"],
                    "state": "open" if mr["state"] == "opened" else mr["state"],
                    "html_url": mr["web_url"],
                    "head_branch": mr["source_branch"],
                    "base_branch": mr["target_branch"],
                    "merged": mr["state"] == "merged",
                    "merged_at": mr.get("merged_at"),
                    "created_at": mr["created_at"],
                    "updated_at": mr["updated_at"],
                    "draft": mr.get("draft", False),
                },
                "error": None,
            }
        except Exception as e:
            return {"found": False, "pr": None, "error": f"Unexpected error: {str(e)}"}

    def get_pr_comments(self, token: str, repo: str, pr_number: int) -> dict[str, Any]:
        try:
            resp = self._api(
                token, "GET",
                f"/projects/{_project_path(repo)}/merge_requests/{pr_number}/notes",
                params={"per_page": 100, "sort": "asc"},
            )

            if resp.status_code != 200:
                return {"comments": [], "total_count": 0, "error": _format_gitlab_error(resp)}

            data = resp.json()
            comments = []
            for note in data:
                # Skip system notes (e.g., "assigned to ...")
                if note.get("system", False):
                    continue
                comments.append({
                    "id": note["id"],
                    "user": note.get("author", {}).get("username", "unknown"),
                    "body": note.get("body", ""),
                    "created_at": note["created_at"],
                    "updated_at": note.get("updated_at"),
                })

            return {"comments": comments, "total_count": len(comments), "error": None}
        except Exception as e:
            return {"comments": [], "total_count": 0, "error": f"Unexpected error: {str(e)}"}

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
        try:
            mr_data: dict[str, Any] = {
                "title": ("Draft: " + title) if draft else title,
                "description": body,
                "source_branch": head,
                "target_branch": base,
            }
            resp = self._api(
                token, "POST",
                f"/projects/{_project_path(repo)}/merge_requests",
                json=mr_data,
            )

            if resp.status_code not in (200, 201):
                return {
                    "success": False,
                    "pr_number": None,
                    "pr_url": None,
                    "error": _format_gitlab_error(resp),
                }

            mr = resp.json()

            # Assign users if provided
            if assignees:
                for username in assignees:
                    try:
                        user_resp = self._api(token, "GET", "/users", params={"username": username})
                        if user_resp.status_code == 200 and user_resp.json():
                            user_id = user_resp.json()[0]["id"]
                            self._api(
                                token, "PUT",
                                f"/projects/{_project_path(repo)}/merge_requests/{mr['iid']}",
                                json={"assignee_ids": [user_id]},
                            )
                    except Exception:
                        pass  # Best-effort assignment

            return {
                "success": True,
                "pr_number": mr["iid"],
                "pr_url": mr["web_url"],
                "error": None,
            }
        except Exception as e:
            return {
                "success": False,
                "pr_number": None,
                "pr_url": None,
                "error": f"Unexpected error: {str(e)}",
            }

    def add_pr_comment(
        self, token: str, repo: str, pr_number: int, body: str
    ) -> dict[str, Any]:
        try:
            resp = self._api(
                token, "POST",
                f"/projects/{_project_path(repo)}/merge_requests/{pr_number}/notes",
                json={"body": body},
            )

            if resp.status_code not in (200, 201):
                return {
                    "success": False,
                    "comment_id": None,
                    "comment_url": None,
                    "error": _format_gitlab_error(resp),
                }

            note = resp.json()
            return {
                "success": True,
                "comment_id": note["id"],
                "comment_url": None,  # GitLab notes don't have individual URLs
                "error": None,
            }
        except Exception as e:
            return {
                "success": False,
                "comment_id": None,
                "comment_url": None,
                "error": f"Unexpected error: {str(e)}",
            }

    # ── File / Content operations ──────────────────────────────────────

    def get_file_content(
        self, token: str, repo: str, branch: str, file_path: str
    ) -> dict[str, Any]:
        try:
            encoded_path = quote_plus(file_path)
            resp = self._api(
                token, "GET",
                f"/projects/{_project_path(repo)}/repository/files/{encoded_path}",
                params={"ref": branch},
            )

            if resp.status_code == 404:
                return {"content": None, "sha": None, "encoding": None, "error": None}

            if resp.status_code != 200:
                return {
                    "content": None,
                    "sha": None,
                    "encoding": None,
                    "error": _format_gitlab_error(resp),
                }

            data = resp.json()
            import base64
            content = base64.b64decode(data["content"]).decode("utf-8")
            return {
                "content": content,
                "sha": data.get("blob_id"),
                "encoding": data.get("encoding", "base64"),
                "error": None,
            }
        except Exception as e:
            return {"content": None, "sha": None, "encoding": None, "error": f"Unexpected error: {str(e)}"}

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
        try:
            import base64
            encoded_path = quote_plus(file_path)
            payload = {
                "branch": branch,
                "content": content,
                "commit_message": message,
                "encoding": "text",
            }

            # Check if file exists to decide PUT vs POST
            method = "PUT" if sha else "POST"
            resp = self._api(
                token, method,
                f"/projects/{_project_path(repo)}/repository/files/{encoded_path}",
                json=payload,
            )

            if resp.status_code not in (200, 201):
                # If POST failed with 400, file may already exist; try PUT
                if method == "POST" and resp.status_code == 400:
                    resp = self._api(
                        token, "PUT",
                        f"/projects/{_project_path(repo)}/repository/files/{encoded_path}",
                        json=payload,
                    )
                if resp.status_code not in (200, 201):
                    return {
                        "success": False,
                        "commit_sha": None,
                        "error": _format_gitlab_error(resp),
                    }

            data = resp.json()
            return {
                "success": True,
                "commit_sha": data.get("blob_id") or data.get("file_path"),
                "error": None,
            }
        except Exception as e:
            return {"success": False, "commit_sha": None, "error": f"Unexpected error: {str(e)}"}

    # ── Branch operations ──────────────────────────────────────────────

    def create_branch(
        self, token: str, repo: str, branch_name: str, base_branch: str
    ) -> dict[str, Any]:
        try:
            resp = self._api(
                token, "POST",
                f"/projects/{_project_path(repo)}/repository/branches",
                json={"branch": branch_name, "ref": base_branch},
            )

            if resp.status_code not in (200, 201):
                return {
                    "success": False,
                    "branch_name": branch_name,
                    "sha": None,
                    "error": _format_gitlab_error(resp),
                }

            data = resp.json()
            return {
                "success": True,
                "branch_name": data["name"],
                "sha": data.get("commit", {}).get("id"),
                "error": None,
            }
        except Exception as e:
            return {
                "success": False,
                "branch_name": branch_name,
                "sha": None,
                "error": f"Unexpected error: {str(e)}",
            }

    # ── CI / Pipeline operations ───────────────────────────────────────

    def get_ci_run_status(self, token: str, repo: str, run_id: str) -> dict[str, Any]:
        try:
            resp = self._api(
                token, "GET",
                f"/projects/{_project_path(repo)}/pipelines/{run_id}",
            )

            if resp.status_code != 200:
                return {
                    "status": "unknown",
                    "conclusion": None,
                    "started_at": None,
                    "completed_at": None,
                    "logs_url": None,
                }

            pipeline = resp.json()
            # Map GitLab statuses to normalized statuses
            gl_status = pipeline.get("status", "unknown")
            conclusion = None
            if gl_status in ("success",):
                conclusion = "success"
            elif gl_status in ("failed",):
                conclusion = "failure"
            elif gl_status in ("canceled",):
                conclusion = "cancelled"

            return {
                "status": "completed" if conclusion else gl_status,
                "conclusion": conclusion,
                "started_at": pipeline.get("started_at"),
                "completed_at": pipeline.get("finished_at"),
                "logs_url": pipeline.get("web_url"),
                "html_url": pipeline.get("web_url"),
            }
        except Exception:
            return {
                "status": "unknown",
                "conclusion": None,
                "started_at": None,
                "completed_at": None,
                "logs_url": None,
            }

    def get_ci_run_logs(
        self, token: str, repo: str, run_id: str, job_name: str | None = None
    ) -> str | None:
        try:
            # Get pipeline jobs
            resp = self._api(
                token, "GET",
                f"/projects/{_project_path(repo)}/pipelines/{run_id}/jobs",
                params={"per_page": 100},
            )

            if resp.status_code != 200:
                return None

            jobs = resp.json()
            log_parts = []

            for job in jobs:
                if job_name and job_name.lower() not in job.get("name", "").lower():
                    continue

                # Get job trace (logs)
                trace_resp = self._api(
                    token, "GET",
                    f"/projects/{_project_path(repo)}/jobs/{job['id']}/trace",
                )
                if trace_resp.status_code == 200:
                    log_parts.append(f"\n=== {job['name']} ===\n")
                    log_parts.append(trace_resp.text)

            return "\n".join(log_parts) if log_parts else None
        except Exception as e:
            logger.error(f"Failed to get GitLab pipeline logs: {e}")
            return None

    def get_check_runs_for_pr(self, token: str, repo: str, pr_number: int) -> list[dict]:
        """Get pipeline runs for a merge request via its head pipeline."""
        try:
            # Get the MR to find the head pipeline
            resp = self._api(
                token, "GET",
                f"/projects/{_project_path(repo)}/merge_requests/{pr_number}",
            )
            if resp.status_code != 200:
                return []

            mr = resp.json()
            pipeline = mr.get("head_pipeline")
            if not pipeline:
                return []

            pipeline_id = pipeline["id"]

            # Get jobs for this pipeline
            jobs_resp = self._api(
                token, "GET",
                f"/projects/{_project_path(repo)}/pipelines/{pipeline_id}/jobs",
                params={"per_page": 100},
            )
            if jobs_resp.status_code != 200:
                return []

            jobs = jobs_resp.json()
            check_runs = []
            for job in jobs:
                gl_status = job.get("status", "unknown")
                conclusion = None
                status = gl_status
                if gl_status in ("success",):
                    conclusion = "success"
                    status = "completed"
                elif gl_status in ("failed",):
                    conclusion = "failure"
                    status = "completed"
                elif gl_status in ("canceled",):
                    conclusion = "cancelled"
                    status = "completed"

                check_runs.append({
                    "id": job["id"],
                    "name": job["name"],
                    "status": status,
                    "conclusion": conclusion,
                    "started_at": job.get("started_at"),
                    "completed_at": job.get("finished_at"),
                    "details_url": job.get("web_url"),
                    "output_title": None,
                    "output_summary": None,
                })

            return check_runs
        except Exception as e:
            logger.error(f"Failed to get GitLab check runs for MR: {e}")
            return []

    # ── URL helpers ────────────────────────────────────────────────────

    def normalize_repository(self, input_str: str) -> str | None:
        if not input_str:
            return None

        trimmed = input_str.strip()

        # Short format: namespace/project (can be nested: group/subgroup/project)
        if re.match(r'^[a-zA-Z0-9_.-]+(/[a-zA-Z0-9_.-]+)+$', trimmed) and "://" not in trimmed and "@" not in trimmed:
            return trimmed

        # HTTPS URL: https://gitlab.com/namespace/project or with .git
        gitlab_host = re.escape(self.gitlab_url.replace("https://", "").replace("http://", ""))
        https_match = re.match(
            rf'^https?://{gitlab_host}/(.+?)(?:\.git)?$',
            trimmed,
        )
        if https_match:
            path = https_match.group(1)
            # Remove trailing slashes and /-/ paths (GitLab UI paths)
            path = re.sub(r'/-/.*$', '', path).rstrip('/')
            return path

        # SSH URL: git@gitlab.com:namespace/project.git
        ssh_match = re.match(
            rf'^git@{gitlab_host.replace("https://", "").replace("http://", "")}:(.+?)(?:\.git)?$',
            trimmed,
        )
        if ssh_match:
            return ssh_match.group(1)

        return None

    def get_clone_url(self, repo: str, token: str) -> str:
        host = self.gitlab_url.replace("https://", "").replace("http://", "")
        return f"https://oauth2:{token}@{host}/{repo}.git"

    def get_repo_web_url(self, repo: str) -> str:
        return f"{self.gitlab_url}/{repo}"
