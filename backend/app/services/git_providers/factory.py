"""Factory for creating Git provider instances."""

from app.services.git_providers.base import GitProvider, GitProviderType
from app.services.git_providers.github_provider import GitHubProvider
from app.services.git_providers.gitlab_provider import GitLabProvider, DEFAULT_GITLAB_URL

# Singleton instances (providers are stateless except for gitlab_url)
_github_provider = GitHubProvider()
_gitlab_providers: dict[str, GitLabProvider] = {}


def get_git_provider(
    provider_type: GitProviderType | str,
    gitlab_url: str = DEFAULT_GITLAB_URL,
) -> GitProvider:
    """
    Get a git provider instance by type.

    Args:
        provider_type: The provider type (github, gitlab)
        gitlab_url: GitLab instance URL (only used for gitlab provider)

    Returns:
        GitProvider instance
    """
    if isinstance(provider_type, str):
        provider_type = GitProviderType(provider_type)

    if provider_type == GitProviderType.GITHUB:
        return _github_provider

    if provider_type == GitProviderType.GITLAB:
        # Cache GitLab providers by URL for self-hosted instances
        if gitlab_url not in _gitlab_providers:
            _gitlab_providers[gitlab_url] = GitLabProvider(gitlab_url)
        return _gitlab_providers[gitlab_url]

    raise ValueError(f"Unsupported git provider type: {provider_type}")


def get_git_provider_for_workspace(workspace) -> GitProvider:
    """
    Get the appropriate git provider for a workspace.

    Reads the workspace's git_provider and gitlab_url fields to
    determine which provider to use.

    Args:
        workspace: Workspace model instance

    Returns:
        GitProvider instance configured for the workspace
    """
    provider_type = getattr(workspace, "git_provider", None) or GitProviderType.GITHUB.value
    gitlab_url = getattr(workspace, "gitlab_url", None) or DEFAULT_GITLAB_URL
    return get_git_provider(provider_type, gitlab_url=gitlab_url)
