"""Workspace management API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.permissions import get_workspace_or_403, require_workspace_admin, require_workspace_owner
from app.database import get_db
from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember, WorkspaceMemberRole
from app.schemas.workspace import (
    AddMemberRequest,
    AddMemberResponse,
    MemberResponse,
    SetDefaultWorkspaceResponse,
    WorkspaceCreate,
    WorkspaceDetail,
    WorkspaceListResponse,
    WorkspaceResponse,
    WorkspaceUpdate,
)
from app.services.workspace_token_service import (
    check_workspace_github_access,
    get_member_github_status,
)
from app.services.encryption_service import decrypt_token
from app.services.git_providers import get_git_provider
from app.services.git_providers.base import GitProviderType
from app.services.workflow_setup_service import WorkflowSetupService

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


def _get_token_for_provider(user: User, provider: str, gitlab_url: str | None = None) -> str:
    """Get the decrypted token for the given provider from the user."""
    if provider == "gitlab":
        if not user.gitlab_token_encrypted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="GitLab account not connected. Please connect your GitLab account first.",
            )
        return decrypt_token(user.gitlab_token_encrypted)
    else:
        if not user.github_token_encrypted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="GitHub account not connected. Please connect your GitHub account first.",
            )
        return decrypt_token(user.github_token_encrypted)


@router.post("/", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
def create_workspace(
    workspace_data: WorkspaceCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Create a new workspace.

    Validates repository and branches before creation.
    Supports both GitHub and GitLab via the `git_provider` field.
    """
    provider = workspace_data.git_provider or "github"
    gitlab_url = workspace_data.gitlab_url

    # Get token and provider instance
    token = _get_token_for_provider(current_user, provider, gitlab_url)
    git_provider = get_git_provider(provider, gitlab_url=gitlab_url or "https://gitlab.com")

    # Normalize repository input
    normalized_repo = git_provider.normalize_repository(workspace_data.github_repository)
    if not normalized_repo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {provider} repository format. Please use owner/repo or a valid URL.",
        )

    # Validate repository
    repo_validation = git_provider.validate_repository(token, normalized_repo)
    if not repo_validation["valid"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=repo_validation.get("error", "Invalid repository"),
        )

    # Validate dev branch
    if not git_provider.validate_branch(token, normalized_repo, workspace_data.github_dev_branch):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Branch '{workspace_data.github_dev_branch}' not found in repository",
        )

    # Validate main branch
    if not git_provider.validate_branch(token, normalized_repo, workspace_data.github_main_branch):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Branch '{workspace_data.github_main_branch}' not found in repository",
        )

    # Create workspace
    workspace = Workspace(
        name=workspace_data.name,
        description=workspace_data.description,
        git_provider=provider,
        gitlab_url=gitlab_url if provider == "gitlab" else None,
        github_repository=normalized_repo,
        github_dev_branch=workspace_data.github_dev_branch,
        github_main_branch=workspace_data.github_main_branch,
        owner_id=current_user.id,
    )
    db.add(workspace)
    db.flush()  # Get workspace ID

    # Check if this is user's first workspace
    existing_memberships = db.query(WorkspaceMember).filter(WorkspaceMember.user_id == current_user.id).count()
    is_first_workspace = existing_memberships == 0

    # Add user as owner
    membership = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=current_user.id,
        role=WorkspaceMemberRole.OWNER.value,
        is_default=is_first_workspace,  # Set as default if first workspace
    )
    db.add(membership)
    db.commit()
    db.refresh(workspace)

    # Build response
    return WorkspaceResponse(
        id=workspace.id,
        name=workspace.name,
        git_provider=workspace.git_provider,
        github_repository=workspace.github_repository,
        github_dev_branch=workspace.github_dev_branch,
        github_main_branch=workspace.github_main_branch,
        is_active=workspace.is_active,
        owner_id=workspace.owner_id,
        created_at=workspace.created_at,
        updated_at=workspace.updated_at,
        role=WorkspaceMemberRole.OWNER.value,
        is_default=is_first_workspace,
    )


@router.get("/", response_model=WorkspaceListResponse)
def list_workspaces(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    skip: int = 0,
    limit: int = 100,
):
    """
    List all workspaces user is a member of.
    """
    # Get user's memberships with workspaces
    memberships = (
        db.query(WorkspaceMember, Workspace)
        .join(Workspace, WorkspaceMember.workspace_id == Workspace.id)
        .filter(WorkspaceMember.user_id == current_user.id)
        .offset(skip)
        .limit(limit)
        .all()
    )

    workspaces = []
    for membership, workspace in memberships:
        workspaces.append(
            WorkspaceResponse(
                id=workspace.id,
                name=workspace.name,
                git_provider=workspace.git_provider or "github",
                github_repository=workspace.github_repository,
                github_dev_branch=workspace.github_dev_branch,
                github_main_branch=workspace.github_main_branch,
                is_active=workspace.is_active,
                owner_id=workspace.owner_id,
                created_at=workspace.created_at,
                updated_at=workspace.updated_at,
                role=membership.role,
                is_default=membership.is_default,
            )
        )

    total = db.query(WorkspaceMember).filter(WorkspaceMember.user_id == current_user.id).count()

    return WorkspaceListResponse(workspaces=workspaces, total=total)


@router.get("/{workspace_id}", response_model=WorkspaceDetail)
def get_workspace(
    workspace_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Get detailed workspace information including members.
    """
    workspace, membership = get_workspace_or_403(workspace_id, db, current_user)

    # Get all members with user details
    members_query = (
        db.query(WorkspaceMember, User)
        .join(User, WorkspaceMember.user_id == User.id)
        .filter(WorkspaceMember.workspace_id == workspace_id)
        .all()
    )

    members = []
    for member_record, user in members_query:
        members.append(
            MemberResponse(
                id=member_record.id,
                user_id=user.id,
                username=user.username,
                email=user.email,
                role=member_record.role,
                joined_at=member_record.joined_at,
            )
        )

    # Get owner details
    owner = db.query(User).filter(User.id == workspace.owner_id).first()

    return WorkspaceDetail(
        id=workspace.id,
        name=workspace.name,
        description=workspace.description,
        git_provider=workspace.git_provider or "github",
        gitlab_url=workspace.gitlab_url,
        github_repository=workspace.github_repository,
        github_dev_branch=workspace.github_dev_branch,
        github_main_branch=workspace.github_main_branch,
        is_active=workspace.is_active,
        owner_id=workspace.owner_id,
        created_at=workspace.created_at,
        updated_at=workspace.updated_at,
        role=membership.role,
        is_default=membership.is_default,
        polling_enabled=workspace.polling_enabled,
        owner={"id": owner.id, "username": owner.username, "email": owner.email},
        members=members,
        member_count=len(members),
    )


@router.put("/{workspace_id}", response_model=WorkspaceDetail)
def update_workspace(
    workspace_id: int,
    workspace_data: WorkspaceUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Update workspace details.

    Requires admin or owner permission.
    Validates branches if changed.
    """
    workspace, membership = require_workspace_admin(workspace_id, db, current_user)

    # Validate branches if being changed
    if workspace_data.github_dev_branch or workspace_data.github_main_branch:
        provider = workspace.git_provider or "github"
        token = _get_token_for_provider(current_user, provider, workspace.gitlab_url)
        git_provider = get_git_provider(provider, gitlab_url=workspace.gitlab_url or "https://gitlab.com")

        if workspace_data.github_dev_branch:
            if not git_provider.validate_branch(token, workspace.github_repository, workspace_data.github_dev_branch):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Branch '{workspace_data.github_dev_branch}' not found",
                )

        if workspace_data.github_main_branch:
            if not git_provider.validate_branch(token, workspace.github_repository, workspace_data.github_main_branch):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Branch '{workspace_data.github_main_branch}' not found",
                )

    # Update fields
    if workspace_data.name is not None:
        workspace.name = workspace_data.name
    if workspace_data.description is not None:
        workspace.description = workspace_data.description
    if workspace_data.github_dev_branch is not None:
        workspace.github_dev_branch = workspace_data.github_dev_branch
    if workspace_data.github_main_branch is not None:
        workspace.github_main_branch = workspace_data.github_main_branch
    if workspace_data.is_active is not None:
        workspace.is_active = workspace_data.is_active

    db.commit()
    db.refresh(workspace)

    # Return detailed view
    return get_workspace(workspace_id, db, current_user)


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workspace(
    workspace_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Delete workspace. Requires owner permission.
    """
    workspace, _ = require_workspace_owner(workspace_id, db, current_user)

    db.delete(workspace)
    db.commit()


@router.post("/{workspace_id}/members", response_model=AddMemberResponse, status_code=status.HTTP_201_CREATED)
def add_member(
    workspace_id: int,
    member_data: AddMemberRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Add a member to workspace.

    Requires admin or owner permission.
    """
    workspace, _ = require_workspace_admin(workspace_id, db, current_user)

    # Check if user exists
    user = db.query(User).filter(User.id == member_data.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Check if already a member
    existing = (
        db.query(WorkspaceMember)
        .filter(WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.user_id == member_data.user_id)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a member of this workspace",
        )

    # Add member
    membership = WorkspaceMember(
        workspace_id=workspace_id,
        user_id=member_data.user_id,
        role=member_data.role,
        is_default=False,
    )
    db.add(membership)
    db.commit()
    db.refresh(membership)

    # Get member's GitHub status
    member_github_status = get_member_github_status(user)

    # Check workspace GitHub access status
    workspace_access = check_workspace_github_access(db, workspace)

    # Build warning message if there are access concerns
    warning = None
    if not workspace_access["has_access"]:
        warning = workspace_access["message"]
    elif not member_github_status["has_github"]:
        provider_name = (workspace.git_provider or "github").capitalize()
        warning = (
            f"Note: {user.username} has not connected their {provider_name} account. "
            "They can still use workspace features through the workspace owner's access, "
            f"but connecting their own {provider_name} account is recommended for the best experience."
        )

    return AddMemberResponse(
        id=membership.id,
        user_id=user.id,
        username=user.username,
        email=user.email,
        role=membership.role,
        joined_at=membership.joined_at,
        has_github=member_github_status["has_github"],
        github_username=member_github_status["github_username"],
        warning=warning,
    )


@router.delete("/{workspace_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    workspace_id: int,
    user_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Remove a member from workspace. Cannot remove the owner.
    """
    workspace, _ = require_workspace_admin(workspace_id, db, current_user)

    # Get membership
    membership = (
        db.query(WorkspaceMember)
        .filter(WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.user_id == user_id)
        .first()
    )

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found in this workspace",
        )

    # Cannot remove owner
    if membership.role == WorkspaceMemberRole.OWNER.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove workspace owner",
        )

    db.delete(membership)
    db.commit()


@router.post("/{workspace_id}/set-default", response_model=SetDefaultWorkspaceResponse)
def set_default_workspace(
    workspace_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Set workspace as user's default.
    """
    _, membership = get_workspace_or_403(workspace_id, db, current_user)

    # Unset all other defaults for this user
    db.query(WorkspaceMember).filter(
        WorkspaceMember.user_id == current_user.id, WorkspaceMember.workspace_id != workspace_id
    ).update({"is_default": False})

    # Set this workspace as default
    membership.is_default = True

    db.commit()

    return SetDefaultWorkspaceResponse(workspace_id=workspace_id, is_default=True)


@router.patch("/{workspace_id}/polling-enabled", status_code=status.HTTP_200_OK)
def toggle_polling_enabled(
    workspace_id: int,
    enabled: bool,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Toggle automatic issue polling for a workspace.
    """
    workspace, membership = get_workspace_or_403(workspace_id, db, current_user)

    # Check if user is admin or owner
    if membership.role not in [WorkspaceMemberRole.ADMIN.value, WorkspaceMemberRole.OWNER.value]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only workspace admins and owners can toggle polling",
        )

    workspace.polling_enabled = enabled
    db.commit()

    return {"workspace_id": workspace_id, "polling_enabled": enabled}


@router.post("/{workspace_id}/setup-workflow", response_model=dict)
def setup_workspace_workflow(
    workspace_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    force_update: bool = Query(False, description="Force update even if workflow exists"),
):
    """
    Setup or update Avery CI workflow in workspace repository.

    Currently only supports GitHub Actions. GitLab CI support coming soon.
    """
    # Get workspace and verify admin access
    workspace, membership = require_workspace_admin(workspace_id, db, current_user)

    provider = workspace.git_provider or "github"
    token = _get_token_for_provider(current_user, provider, workspace.gitlab_url)

    # Setup workflow using the service
    service = WorkflowSetupService(db)

    # Get backend URL from settings
    from app.core.config import settings
    webhook_base_url = settings.BACKEND_URL

    result = service.setup_workflow(
        workspace=workspace,
        github_token=token,
        avery_webhook_url=webhook_base_url,
        force_update=force_update,
    )

    if result["status"] == "error":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result["message"],
        )

    # Get setup instructions
    instructions = service.get_setup_instructions(
        workspace=workspace,
        api_token=settings.AVERY_API_TOKEN if settings.AVERY_API_TOKEN else "<GENERATE_API_TOKEN>",
        webhook_url=f"{webhook_base_url}/api/v1/ci/webhook",
    )

    return {
        "workflow": result,
        "instructions": instructions,
    }
