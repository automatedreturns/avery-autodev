"""Git operations tools."""

import subprocess
from pathlib import Path

from .base import AgentTool, ToolContext, ToolResult


class GetGitDiffTool(AgentTool):
    """Get git diff of changes in working directory."""

    @property
    def name(self) -> str:
        return "get_git_diff"

    @property
    def description(self) -> str:
        return """View git diff of changes in the working directory.
Use this to review what changes have been made before committing.
Returns the diff showing added/removed/modified lines."""

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Optional: specific file to diff (shows all changes if empty)"
                },
                "staged": {
                    "type": "boolean",
                    "description": "Show only staged changes (default: false, shows unstaged)"
                },
                "stat": {
                    "type": "boolean",
                    "description": "Show summary statistics only (default: false)"
                }
            },
            "required": []
        }

    def execute(self, params: dict, context: ToolContext) -> ToolResult:
        """Execute git diff."""
        file_path = params.get("file_path")
        staged = params.get("staged", False)
        stat = params.get("stat", False)

        try:
            cmd = ["git", "diff"]

            if staged:
                cmd.append("--staged")

            if stat:
                cmd.append("--stat")

            if file_path:
                cmd.append("--")
                cmd.append(file_path)

            result = subprocess.run(
                cmd,
                cwd=context.repo_path,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                return ToolResult(
                    success=False,
                    data={},
                    error=f"Git diff failed: {result.stderr}"
                )

            diff_output = result.stdout

            if not diff_output.strip():
                return ToolResult(
                    success=True,
                    data={
                        "has_changes": False,
                        "diff": "",
                        "message": "No changes detected"
                    }
                )

            # Parse diff for summary
            files_changed = self._parse_diff_files(diff_output)

            return ToolResult(
                success=True,
                data={
                    "has_changes": True,
                    "diff": diff_output[:5000],  # Limit to 5000 chars
                    "files_changed": files_changed,
                    "truncated": len(diff_output) > 5000
                }
            )

        except Exception as e:
            return ToolResult(
                success=False,
                data={},
                error=f"Git diff failed: {str(e)}"
            )

    def _parse_diff_files(self, diff_output: str) -> list[str]:
        """Parse list of files from diff output."""
        files = []
        for line in diff_output.split('\n'):
            if line.startswith('diff --git'):
                # Format: diff --git a/file b/file
                parts = line.split()
                if len(parts) >= 4:
                    file_path = parts[2][2:]  # Remove 'a/' prefix
                    files.append(file_path)
        return files


class GitStatusTool(AgentTool):
    """Get current git status showing modified/added/deleted files."""

    @property
    def name(self) -> str:
        return "git_status"

    @property
    def description(self) -> str:
        return """Get current git repository status.
Shows which files are modified, staged, untracked, or deleted.
Useful for understanding the current state before making changes."""

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {},
            "required": []
        }

    def execute(self, params: dict, context: ToolContext) -> ToolResult:
        """Execute git status."""
        try:
            # Get status in porcelain format for easy parsing
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=context.repo_path,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                return ToolResult(
                    success=False,
                    data={},
                    error=f"Git status failed: {result.stderr}"
                )

            # Parse status
            status = self._parse_status(result.stdout)

            # Get current branch
            branch_result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=context.repo_path,
                capture_output=True,
                text=True,
                timeout=5
            )

            current_branch = branch_result.stdout.strip()

            return ToolResult(
                success=True,
                data={
                    "branch": current_branch,
                    "modified": status["modified"],
                    "staged": status["staged"],
                    "untracked": status["untracked"],
                    "deleted": status["deleted"],
                    "clean": len(status["modified"]) == 0 and len(status["untracked"]) == 0
                }
            )

        except Exception as e:
            return ToolResult(
                success=False,
                data={},
                error=f"Git status failed: {str(e)}"
            )

    def _parse_status(self, output: str) -> dict:
        """Parse git status porcelain output."""
        status = {
            "modified": [],
            "staged": [],
            "untracked": [],
            "deleted": []
        }

        for line in output.split('\n'):
            if not line.strip():
                continue

            # Format: XY filename
            # X = staged status, Y = unstaged status
            if len(line) < 3:
                continue

            x, y = line[0], line[1]
            filename = line[3:]

            # Staged changes
            if x in ('M', 'A', 'D', 'R', 'C'):
                status["staged"].append(filename)

            # Unstaged changes
            if y == 'M':
                status["modified"].append(filename)
            elif y == 'D':
                status["deleted"].append(filename)

            # Untracked
            if x == '?' and y == '?':
                status["untracked"].append(filename)

        return status
