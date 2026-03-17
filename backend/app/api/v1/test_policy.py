"""
Phase 2: Test Policy API endpoints.

Provides endpoints for managing workspace test policies and policy enforcement.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.permissions import get_workspace_or_403, require_workspace_admin
from app.database import get_db
from app.models.user import User
from app.schemas.test_policy import (
    PolicyDecisionResponse,
    PolicyEnforcementRequest,
    PolicyRecommendationsResponse,
    PolicyRecommendationResponse,
    TestPolicyResponse,
    TestPolicyUpdate,
)

router = APIRouter(prefix="/{workspace_id}/test-policy", tags=["test-policy"])


@router.get("", response_model=TestPolicyResponse)
def get_test_policy(
    workspace_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Get test policy configuration for a workspace.

    Args:
        workspace_id: Workspace ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        Test policy configuration

    Raises:
        HTTPException: If user is not a workspace member
    """
    workspace, _ = get_workspace_or_403(workspace_id, db, current_user)

    return TestPolicyResponse(
        workspace_id=workspace.id,
        test_policy_enabled=workspace.test_policy_enabled,
        test_policy_config=workspace.test_policy_config,
    )


@router.put("", response_model=TestPolicyResponse)
def update_test_policy(
    workspace_id: int,
    policy_update: TestPolicyUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Update test policy configuration for a workspace.

    Requires admin or owner permission.

    Args:
        workspace_id: Workspace ID
        policy_update: Updated policy configuration
        db: Database session
        current_user: Current authenticated user

    Returns:
        Updated test policy configuration

    Raises:
        HTTPException: If user lacks admin permission
    """
    workspace, _ = require_workspace_admin(workspace_id, db, current_user)

    # Get current config
    config = workspace.test_policy_config.copy()

    # Update fields that are provided
    if policy_update.require_tests_for_features is not None:
        config["require_tests_for_features"] = policy_update.require_tests_for_features
    if policy_update.require_tests_for_bug_fixes is not None:
        config["require_tests_for_bug_fixes"] = policy_update.require_tests_for_bug_fixes
    if policy_update.minimum_coverage_percent is not None:
        config["minimum_coverage_percent"] = policy_update.minimum_coverage_percent
    if policy_update.allow_coverage_decrease is not None:
        config["allow_coverage_decrease"] = policy_update.allow_coverage_decrease
    if policy_update.max_coverage_decrease_percent is not None:
        config["max_coverage_decrease_percent"] = policy_update.max_coverage_decrease_percent
    if policy_update.require_edge_case_tests is not None:
        config["require_edge_case_tests"] = policy_update.require_edge_case_tests
    if policy_update.require_integration_tests is not None:
        config["require_integration_tests"] = policy_update.require_integration_tests
    if policy_update.test_quality_threshold is not None:
        config["test_quality_threshold"] = policy_update.test_quality_threshold
    if policy_update.auto_generate_tests is not None:
        config["auto_generate_tests"] = policy_update.auto_generate_tests
    if policy_update.test_frameworks is not None:
        config["test_frameworks"] = {
            "backend": policy_update.test_frameworks.backend,
            "frontend": policy_update.test_frameworks.frontend,
        }

    # Update workspace
    workspace.test_policy_config = config
    db.commit()
    db.refresh(workspace)

    return TestPolicyResponse(
        workspace_id=workspace.id,
        test_policy_enabled=workspace.test_policy_enabled,
        test_policy_config=workspace.test_policy_config,
    )


@router.patch("/enabled", response_model=TestPolicyResponse)
def toggle_test_policy_enabled(
    workspace_id: int,
    enabled: bool,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Enable or disable test policy enforcement for a workspace.

    Requires admin or owner permission.

    Args:
        workspace_id: Workspace ID
        enabled: True to enable, False to disable
        db: Database session
        current_user: Current authenticated user

    Returns:
        Updated test policy configuration

    Raises:
        HTTPException: If user lacks admin permission
    """
    workspace, _ = require_workspace_admin(workspace_id, db, current_user)

    workspace.test_policy_enabled = enabled
    db.commit()
    db.refresh(workspace)

    return TestPolicyResponse(
        workspace_id=workspace.id,
        test_policy_enabled=workspace.test_policy_enabled,
        test_policy_config=workspace.test_policy_config,
    )
