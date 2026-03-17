"""Git provider utility functions (GitHub & GitLab)."""

import re


def normalize_github_repository(input_str: str) -> str | None:
    """
    Normalize GitHub repository input to owner/repo format.

    Supports:
    - Full URLs: https://github.com/owner/repo
    - Full URLs with .git: https://github.com/owner/repo.git
    - SSH URLs: git@github.com:owner/repo.git
    - Short format: owner/repo

    Args:
        input_str: GitHub repository URL or short format

    Returns:
        Normalized owner/repo format or None if invalid
    """
    if not input_str:
        return None

    trimmed = input_str.strip()

    # Short format: owner/repo
    if re.match(r'^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$', trimmed):
        return trimmed

    # HTTPS URL: https://github.com/owner/repo or https://github.com/owner/repo.git
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


def normalize_gitlab_repository(input_str: str, gitlab_url: str = "https://gitlab.com") -> str | None:
    """
    Normalize GitLab repository input to namespace/project format.

    Supports:
    - Full URLs: https://gitlab.com/namespace/project
    - Full URLs with .git: https://gitlab.com/namespace/project.git
    - SSH URLs: git@gitlab.com:namespace/project.git
    - Short format: namespace/project (including nested groups)

    Args:
        input_str: GitLab repository URL or short format
        gitlab_url: GitLab instance URL for matching

    Returns:
        Normalized namespace/project format or None if invalid
    """
    if not input_str:
        return None

    trimmed = input_str.strip()

    # Short format: namespace/project (can include nested groups)
    if re.match(r'^[a-zA-Z0-9_.-]+(/[a-zA-Z0-9_.-]+)+$', trimmed) and "://" not in trimmed and "@" not in trimmed:
        return trimmed

    # Extract host from gitlab_url for pattern matching
    host = gitlab_url.replace("https://", "").replace("http://", "").rstrip("/")
    escaped_host = re.escape(host)

    # HTTPS URL
    https_match = re.match(
        rf'^https?://{escaped_host}/(.+?)(?:\.git)?$',
        trimmed,
    )
    if https_match:
        path = https_match.group(1)
        path = re.sub(r'/-/.*$', '', path).rstrip('/')
        return path

    # SSH URL
    ssh_match = re.match(
        rf'^git@{escaped_host}:(.+?)(?:\.git)?$',
        trimmed,
    )
    if ssh_match:
        return ssh_match.group(1)

    return None


def normalize_repository(input_str: str, provider: str = "github", gitlab_url: str = "https://gitlab.com") -> str | None:
    """
    Normalize a repository input based on the provider type.

    Args:
        input_str: Repository URL or short format
        provider: Git provider ("github" or "gitlab")
        gitlab_url: GitLab instance URL (only for gitlab provider)

    Returns:
        Normalized repository string or None if invalid
    """
    if provider == "gitlab":
        return normalize_gitlab_repository(input_str, gitlab_url)
    return normalize_github_repository(input_str)
