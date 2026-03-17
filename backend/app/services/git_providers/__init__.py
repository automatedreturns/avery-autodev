"""Git provider abstraction layer for multi-platform support (GitHub, GitLab)."""

from app.services.git_providers.base import GitProvider, GitProviderType
from app.services.git_providers.factory import get_git_provider, get_git_provider_for_workspace

__all__ = [
    "GitProvider",
    "GitProviderType",
    "get_git_provider",
    "get_git_provider_for_workspace",
]
