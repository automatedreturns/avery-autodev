"""Local Git operations service for managing repository clones and branches."""

import os
import subprocess
from pathlib import Path
from typing import Optional

from app.core.config import settings


class GitLocalError(Exception):
    """Exception raised for Git operation errors."""
    pass


def get_task_repo_path(workspace_id: int, task_id: int, base_path: str | None = None) -> str:
    """
    Generate a unique local repository path for a task.

    Args:
        workspace_id: Workspace ID
        task_id: Task ID
        base_path: Base directory for all task repositories (optional, uses config default)

    Returns:
        Absolute path for the task's repository clone
    """
    if base_path is None:
        base_path = settings.REPOS_BASE_PATH
    return str(Path(base_path) / f"workspace-{workspace_id}" / f"task-{task_id}")


def ensure_repo_cloned(repo_path: str, repo_url: str, token: str, auth_clone_url: str | None = None) -> None:
    """
    Ensure repository is cloned locally. Clone if doesn't exist, pull if it does.

    Args:
        repo_path: Local path where repository should be cloned
        repo_url: Repository path (format: "owner/repo" or "group/subgroup/project")
        token: Git personal access token
        auth_clone_url: Pre-built authenticated clone URL. If provided, used directly
                        instead of constructing from token + github.com.

    Raises:
        GitLocalError: If clone or pull fails
    """
    repo_dir = Path(repo_path)
    auth_url = auth_clone_url or f"https://{token}@github.com/{repo_url}.git"
    
    try:
        if repo_dir.exists() and (repo_dir / ".git").exists():
            # Repository already exists, pull latest
            _run_git_command(["git", "fetch", "--all"], cwd=repo_path)
        else:
            # Clone repository
            repo_dir.parent.mkdir(parents=True, exist_ok=True)
            _run_git_command(["git", "clone", auth_url, str(repo_dir)])
    except subprocess.CalledProcessError as e:
        raise GitLocalError(f"Failed to clone/update repository: {e.stderr}")


def create_branch(repo_path: str, branch_name: str, base_branch: str = "main") -> None:
    """
    Create a new branch from base branch.

    Args:
        repo_path: Local repository path
        branch_name: Name of new branch to create
        base_branch: Base branch to create from (default: "main")

    Raises:
        GitLocalError: If branch creation fails
    """
    try:
        # Fetch latest changes
        _run_git_command(["git", "fetch", "origin"], cwd=repo_path)

        # Checkout base branch and pull
        _run_git_command(["git", "checkout", base_branch], cwd=repo_path)
        _run_git_command(["git", "pull", "origin", base_branch], cwd=repo_path)

        # Create and checkout new branch
        _run_git_command(["git", "checkout", "-b", branch_name], cwd=repo_path)
    except subprocess.CalledProcessError as e:
        raise GitLocalError(f"Failed to create branch: {e.stderr}")


def checkout_branch(repo_path: str, branch_name: str) -> None:
    """
    Checkout an existing branch.

    Args:
        repo_path: Local repository path
        branch_name: Branch name to checkout

    Raises:
        GitLocalError: If checkout fails
    """
    try:
        _run_git_command(["git", "checkout", branch_name], cwd=repo_path)
    except subprocess.CalledProcessError as e:
        raise GitLocalError(f"Failed to checkout branch: {e.stderr}")


def checkout_remote_branch(repo_path: str, branch_name: str, remote: str = "origin") -> None:
    """
    Checkout a remote branch, creating a local tracking branch.

    Args:
        repo_path: Local repository path
        branch_name: Branch name to checkout (without remote prefix)
        remote: Remote name (default: "origin")

    Raises:
        GitLocalError: If checkout fails
    """
    try:
        # First, try the simpler approach: git checkout branch_name
        # Modern git will automatically set up tracking if a remote branch exists
        try:
            _run_git_command(["git", "checkout", branch_name], cwd=repo_path)
            return
        except subprocess.CalledProcessError:
            # If that fails, try creating with explicit tracking
            pass

        # Try creating local tracking branch from remote
        _run_git_command(
            ["git", "checkout", "-b", branch_name, "--track", f"{remote}/{branch_name}"],
            cwd=repo_path
        )
    except subprocess.CalledProcessError as e:
        # Get list of remote branches for debugging
        try:
            result = _run_git_command(["git", "branch", "-r"], cwd=repo_path)
            remote_branches = result.stdout
            raise GitLocalError(
                f"Failed to checkout remote branch '{branch_name}'. "
                f"Error: {e.stderr}. "
                f"Available remote branches: {remote_branches}"
            )
        except:
            raise GitLocalError(f"Failed to checkout remote branch '{branch_name}': {e.stderr}")


def fetch(repo_path: str, remote: str = "origin") -> None:
    """
    Fetch latest changes from remote without merging.

    Args:
        repo_path: Local repository path
        remote: Remote name (default: "origin")

    Raises:
        GitLocalError: If fetch fails
    """
    try:
        # Fetch all branches and tags from remote
        _run_git_command(["git", "fetch", remote, "--prune"], cwd=repo_path)
    except subprocess.CalledProcessError as e:
        raise GitLocalError(f"Failed to fetch from remote: {e.stderr}")


def fetch_pull_request(repo_path: str, pr_number: int, branch_name: str, remote: str = "origin") -> None:
    """
    Fetch a pull request and create a local branch for it.

    This works for both regular PRs and PRs from forks by fetching the PR's ref directly.

    Args:
        repo_path: Local repository path
        pr_number: Pull request number
        branch_name: Local branch name to create
        remote: Remote name (default: "origin")

    Raises:
        GitLocalError: If fetch fails
    """
    try:
        # Fetch the PR ref from GitHub
        # GitHub exposes all PRs as refs/pull/<number>/head
        _run_git_command(
            ["git", "fetch", remote, f"pull/{pr_number}/head:{branch_name}"],
            cwd=repo_path
        )
    except subprocess.CalledProcessError as e:
        raise GitLocalError(f"Failed to fetch pull request #{pr_number}: {e.stderr}")


def pull(repo_path: str, remote: str = "origin", branch: str | None = None) -> None:
    """
    Pull latest changes from remote and merge into current branch.

    Args:
        repo_path: Local repository path
        remote: Remote name (default: "origin")
        branch: Branch name to pull (default: current branch)

    Raises:
        GitLocalError: If pull fails
    """
    try:
        if branch:
            _run_git_command(["git", "pull", remote, branch], cwd=repo_path)
        else:
            _run_git_command(["git", "pull"], cwd=repo_path)
    except subprocess.CalledProcessError as e:
        raise GitLocalError(f"Failed to pull changes: {e.stderr}")


def configure_git_user(repo_path: str, name: str = "Avery Agent", email: str = "agent@avery.dev") -> None:
    """
    Configure git user for commits.

    Args:
        repo_path: Local repository path
        name: Git user name (default: "Avery Agent")
        email: Git user email (default: "agent@avery.dev")

    Raises:
        GitLocalError: If configuration fails
    """
    try:
        _run_git_command(["git", "config", "user.name", name], cwd=repo_path)
        _run_git_command(["git", "config", "user.email", email], cwd=repo_path)
    except subprocess.CalledProcessError as e:
        raise GitLocalError(f"Failed to configure git user: {e.stderr}")


def commit_changes(repo_path: str, message: str, files: Optional[list[str]] = None) -> None:
    """
    Commit changes to the current branch.

    Args:
        repo_path: Local repository path
        message: Commit message
        files: Optional list of specific files to commit (default: all changes)

    Raises:
        GitLocalError: If commit fails
    """
    try:
        if files:
            # Add specific files
            for file in files:
                _run_git_command(["git", "add", file], cwd=repo_path)
        else:
            # Add all changes
            _run_git_command(["git", "add", "."], cwd=repo_path)

        _run_git_command(["git", "commit", "-m", message], cwd=repo_path)
    except subprocess.CalledProcessError as e:
        raise GitLocalError(f"Failed to commit changes: {e.stderr}")


def push_branch(
    repo_path: str,
    branch_name: str,
    token: str,
    repo_url: str,
    set_upstream: bool = True
) -> None:
    """
    Push branch to remote.

    Args:
        repo_path: Local repository path
        branch_name: Branch name to push
        token: GitHub personal access token
        repo_url: Repository URL in format "owner/repo"
        set_upstream: Set upstream tracking (default: True)

    Raises:
        GitLocalError: If push fails
    """
    try:
        # Set authenticated remote URL before pushing
        auth_url = f"https://{token}@github.com/{repo_url}.git"
        _run_git_command(["git", "remote", "set-url", "origin", auth_url], cwd=repo_path)

        # Now push with authentication
        if set_upstream:
            _run_git_command(["git", "push", "-u", "origin", branch_name], cwd=repo_path)
        else:
            _run_git_command(["git", "push", "origin", branch_name], cwd=repo_path)
    except subprocess.CalledProcessError as e:
        raise GitLocalError(f"Failed to push branch: {e.stderr}")


def read_file(repo_path: str, file_path: str) -> str:
    """
    Read file contents from local repository.

    Args:
        repo_path: Local repository path
        file_path: Relative path to file within repository

    Returns:
        File contents as string

    Raises:
        GitLocalError: If file doesn't exist or can't be read
    """
    full_path = Path(repo_path) / file_path

    if not full_path.exists():
        raise GitLocalError(f"File not found: {file_path}")

    if not full_path.is_file():
        raise GitLocalError(f"Path is not a file: {file_path}")

    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        # Try reading as binary and decode with errors='replace'
        with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()
    except Exception as e:
        raise GitLocalError(f"Failed to read file: {str(e)}")


def write_file(repo_path: str, file_path: str, content: str) -> None:
    """
    Write content to file in local repository.

    Args:
        repo_path: Local repository path
        file_path: Relative path to file within repository
        content: Content to write

    Raises:
        GitLocalError: If write fails
    """
    full_path = Path(repo_path) / file_path

    try:
        # Create parent directories if needed
        full_path.parent.mkdir(parents=True, exist_ok=True)

        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
    except Exception as e:
        raise GitLocalError(f"Failed to write file: {str(e)}")


def list_directory(repo_path: str, dir_path: str = ".") -> list[dict]:
    """
    List directory contents in local repository.

    Args:
        repo_path: Local repository path
        dir_path: Relative directory path within repository (default: ".")

    Returns:
        List of dicts with 'name', 'type' ('file' or 'dir'), and 'path' keys

    Raises:
        GitLocalError: If directory doesn't exist or can't be listed
    """
    full_path = Path(repo_path) / dir_path

    if not full_path.exists():
        raise GitLocalError(f"Directory not found: {dir_path}")

    if not full_path.is_dir():
        raise GitLocalError(f"Path is not a directory: {dir_path}")

    try:
        items = []
        for item in full_path.iterdir():
            # Skip .git directory
            if item.name == '.git':
                continue

            rel_path = str(item.relative_to(repo_path))
            items.append({
                'name': item.name,
                'type': 'dir' if item.is_dir() else 'file',
                'path': rel_path
            })

        return sorted(items, key=lambda x: (x['type'] != 'dir', x['name']))
    except Exception as e:
        raise GitLocalError(f"Failed to list directory: {str(e)}")


def get_file_tree(repo_path: str, max_depth: int = 3) -> str:
    """
    Get a tree representation of repository structure.

    Args:
        repo_path: Local repository path
        max_depth: Maximum depth to traverse (default: 3)

    Returns:
        Tree structure as string
    """
    def build_tree(path: Path, prefix: str = "", depth: int = 0) -> list[str]:
        if depth >= max_depth:
            return []

        lines = []
        try:
            items = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name))
            # Filter out .git and common ignore patterns
            items = [
                item for item in items
                if item.name not in {'.git', '__pycache__', 'node_modules', '.venv', 'venv', '.env'}
            ]

            for i, item in enumerate(items):
                is_last = i == len(items) - 1
                current_prefix = "└── " if is_last else "├── "
                lines.append(f"{prefix}{current_prefix}{item.name}")

                if item.is_dir():
                    extension = "    " if is_last else "│   "
                    lines.extend(build_tree(item, prefix + extension, depth + 1))
        except PermissionError:
            pass

        return lines

    tree_lines = [Path(repo_path).name]
    tree_lines.extend(build_tree(Path(repo_path)))
    return "\n".join(tree_lines)


def get_file_tree_recursive(repo_path: str, max_depth: int = 10) -> list[dict]:
    """
    Get recursive file tree structure for file browser.

    Args:
        repo_path: Local repository path
        max_depth: Maximum depth to traverse (default: 10)

    Returns:
        List of dicts with nested 'children' for directories:
        [
            {
                'name': 'src',
                'path': 'src',
                'type': 'dir',
                'children': [...]
            },
            {
                'name': 'README.md',
                'path': 'README.md',
                'type': 'file',
                'size': 1234
            }
        ]

    Raises:
        GitLocalError: If repo_path doesn't exist or can't be read
    """
    # Patterns to exclude
    EXCLUDE_PATTERNS = {
        '.git', '__pycache__', 'node_modules', '.venv', 'venv',
        '.env', '.DS_Store', '.pytest_cache', 'dist', 'build',
        '*.pyc', '*.pyo', '*.pyd', '.Python', 'pip-log.txt',
        'pip-delete-this-directory.txt', '.tox', '.coverage',
        '.eggs', '*.egg-info', '*.egg', '.idea', '.vscode'
    }

    def should_exclude(name: str) -> bool:
        """Check if file/folder should be excluded."""
        if name in EXCLUDE_PATTERNS:
            return True
        # Check for pattern matches (e.g., *.pyc)
        for pattern in EXCLUDE_PATTERNS:
            if '*' in pattern:
                suffix = pattern.replace('*', '')
                if name.endswith(suffix):
                    return True
        return False

    def build_tree_recursive(path: Path, depth: int = 0) -> list[dict]:
        """Recursively build tree structure."""
        if depth >= max_depth:
            return []

        try:
            items = []
            entries = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))

            for entry in entries:
                # Skip excluded patterns
                if should_exclude(entry.name):
                    continue

                # Get relative path from repo root
                try:
                    rel_path = str(entry.relative_to(repo_path))
                except ValueError:
                    # Entry is not relative to repo_path, skip it
                    continue

                if entry.is_dir():
                    # Recursively get children for directories
                    children = build_tree_recursive(entry, depth + 1)
                    items.append({
                        'name': entry.name,
                        'path': rel_path,
                        'type': 'dir',
                        'children': children
                    })
                else:
                    # Get file size
                    try:
                        size = entry.stat().st_size
                    except OSError:
                        size = 0

                    items.append({
                        'name': entry.name,
                        'path': rel_path,
                        'type': 'file',
                        'size': size
                    })

            return items
        except PermissionError:
            return []
        except Exception as e:
            raise GitLocalError(f"Failed to build file tree: {str(e)}")

    repo_dir = Path(repo_path)

    if not repo_dir.exists():
        raise GitLocalError(f"Repository path does not exist: {repo_path}")

    if not repo_dir.is_dir():
        raise GitLocalError(f"Repository path is not a directory: {repo_path}")

    return build_tree_recursive(repo_dir)


def branch_exists(repo_path: str, branch_name: str) -> bool:
    """
    Check if a branch exists locally.

    Args:
        repo_path: Local repository path
        branch_name: Branch name to check

    Returns:
        True if branch exists, False otherwise
    """
    try:
        result = _run_git_command(
            ["git", "rev-parse", "--verify", branch_name],
            cwd=repo_path,
            capture_output=True
        )
        return True
    except subprocess.CalledProcessError:
        return False


def get_current_branch(repo_path: str) -> str:
    """
    Get the name of the current branch.

    Args:
        repo_path: Local repository path

    Returns:
        Current branch name

    Raises:
        GitLocalError: If unable to determine current branch
    """
    try:
        result = _run_git_command(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_path,
            capture_output=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise GitLocalError(f"Failed to get current branch: {e.stderr}")


def get_branch_diff(repo_path: str, base_branch: str, compare_branch: str | None = None) -> dict:
    """
    Get the diff between two branches.

    Args:
        repo_path: Local repository path
        base_branch: Base branch to compare against
        compare_branch: Branch to compare (default: current branch)

    Returns:
        Dict with 'files' (list of changed files) and 'diff' (full diff text)

    Raises:
        GitLocalError: If diff operation fails
    """
    try:
        # Fetch latest to ensure we have up-to-date refs
        _run_git_command(["git", "fetch", "origin"], cwd=repo_path)

        # Get current branch if compare_branch not specified
        if compare_branch is None:
            compare_branch = get_current_branch(repo_path)

        # Get list of changed files
        files_result = _run_git_command(
            ["git", "diff", "--name-status", f"origin/{base_branch}...{compare_branch}"],
            cwd=repo_path,
            capture_output=True
        )

        changed_files = []
        for line in files_result.stdout.strip().split('\n'):
            if not line:
                continue
            parts = line.split('\t', 1)
            if len(parts) == 2:
                status, filepath = parts
                changed_files.append({
                    'status': status,  # A (added), M (modified), D (deleted)
                    'path': filepath
                })

        # Get full diff
        diff_result = _run_git_command(
            ["git", "diff", f"origin/{base_branch}...{compare_branch}"],
            cwd=repo_path,
            capture_output=True
        )

        return {
            'files': changed_files,
            'diff': diff_result.stdout
        }
    except subprocess.CalledProcessError as e:
        raise GitLocalError(f"Failed to get branch diff: {e.stderr}")


def _run_git_command(
    cmd: list[str],
    cwd: Optional[str] = None,
    capture_output: bool = False
) -> subprocess.CompletedProcess:
    """
    Run a git command.

    Args:
        cmd: Command and arguments as list
        cwd: Working directory (default: None)
        capture_output: Capture stdout/stderr (default: False)

    Returns:
        CompletedProcess instance

    Raises:
        subprocess.CalledProcessError: If command fails
    """
    if capture_output:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True
        )
    else:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True
        )

    return result
