"""Git provider integration API endpoints (GitHub & GitLab)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.github import GitHubBranchList, GitHubRepoValidation, GitHubTokenResponse, GitHubTokenStore
from app.services.encryption_service import decrypt_token, encrypt_token
from app.services.git_providers import get_git_provider
from app.services.git_providers.base import GitProviderType

router = APIRouter(prefix="/github", tags=["github"])


def _get_provider_token_and_instance(current_user: User, provider: str = "github", gitlab_url: str | None = None):
    """Helper to get the token and provider instance for the given provider type."""
    if provider == "gitlab":
        if not current_user.gitlab_token_encrypted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="GitLab account not connected. Please connect your GitLab account first.",
            )
        token = decrypt_token(current_user.gitlab_token_encrypted)
        git_provider = get_git_provider(GitProviderType.GITLAB, gitlab_url=gitlab_url or current_user.gitlab_url or "https://gitlab.com")
    else:
        if not current_user.github_token_encrypted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="GitHub account not connected. Please connect your GitHub account first.",
            )
        token = decrypt_token(current_user.github_token_encrypted)
        git_provider = get_git_provider(GitProviderType.GITHUB)

    return token, git_provider


@router.post("/token", response_model=GitHubTokenResponse)
def store_github_token(
    token_data: GitHubTokenStore,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Store or update user's git provider personal access token.

    Supports both GitHub and GitLab tokens via the `provider` field.
    """
    provider = token_data.provider or "github"
    git_provider = get_git_provider(
        provider,
        gitlab_url=token_data.gitlab_url or "https://gitlab.com",
    )

    # Get username if not provided
    username = token_data.github_username
    if not username:
        username = git_provider.get_username(token_data.token)
        if not username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid {provider} token or unable to fetch username",
            )

    # Encrypt and store token
    encrypted_token = encrypt_token(token_data.token)

    if provider == "gitlab":
        current_user.gitlab_token_encrypted = encrypted_token
        current_user.gitlab_username = username
        current_user.gitlab_url = token_data.gitlab_url
    else:
        current_user.github_token_encrypted = encrypted_token
        current_user.github_username = username

    db.commit()
    db.refresh(current_user)

    return GitHubTokenResponse(status="connected", github_username=username, provider=provider)


@router.delete("/token", status_code=status.HTTP_204_NO_CONTENT)
def remove_github_token(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    provider: str = Query(default="github", pattern=r"^(github|gitlab)$"),
):
    """
    Remove user's stored git provider token.

    Pass `provider=gitlab` query param to remove GitLab token instead.
    """
    if provider == "gitlab":
        current_user.gitlab_token_encrypted = None
        current_user.gitlab_username = None
        current_user.gitlab_url = None
    else:
        current_user.github_token_encrypted = None
        current_user.github_username = None

    db.commit()


@router.get("/validate-repo", response_model=GitHubRepoValidation)
def validate_repo(
    repo: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    provider: str = Query(default="github", pattern=r"^(github|gitlab)$"),
    gitlab_url: str | None = Query(default=None),
):
    """
    Validate that repository exists and user has access.

    Supports both GitHub and GitLab repositories via the `provider` query param.
    """
    token, git_provider = _get_provider_token_and_instance(current_user, provider, gitlab_url)

    # Normalize repository input
    normalized_repo = git_provider.normalize_repository(repo)
    if not normalized_repo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {provider} repository format. Please use owner/repo or a valid URL.",
        )

    # Validate repository
    result = git_provider.validate_repository(token, normalized_repo)

    return GitHubRepoValidation(**result)


@router.get("/branches", response_model=GitHubBranchList)
def get_branches(
    repo: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    refresh: bool = False,
    provider: str = Query(default="github", pattern=r"^(github|gitlab)$"),
    gitlab_url: str | None = Query(default=None),
):
    """
    List all branches for a repository.

    Supports both GitHub and GitLab repositories via the `provider` query param.
    """
    token, git_provider = _get_provider_token_and_instance(current_user, provider, gitlab_url)

    # Normalize repository input
    normalized_repo = git_provider.normalize_repository(repo)
    if not normalized_repo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {provider} repository format. Please use owner/repo or a valid URL.",
        )

    # List branches
    result = git_provider.list_branches(token, normalized_repo, skip_cache=refresh)

    if result.get("error"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["error"],
        )

    return GitHubBranchList(**result)
