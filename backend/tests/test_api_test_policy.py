"""
Tests for Phase 2 test policy API endpoints.

Tests cover:
- GET /workspaces/{workspace_id}/test-policy
- PUT /workspaces/{workspace_id}/test-policy
- PATCH /workspaces/{workspace_id}/test-policy/enabled
"""

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.main import app
from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember, WorkspaceMemberRole
from app.schemas.test_policy import TestPolicyConfig, TestFrameworksConfig


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def test_user(db_session):
    """Create a test user."""
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password="hashed_password",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_workspace(db_session, test_user):
    """Create a test workspace."""
    workspace = Workspace(
        name="Test Workspace",
        description="Test workspace for API tests",
        github_repository="owner/repo",
        github_dev_branch="dev",
        github_main_branch="main",
        owner_id=test_user.id,
        test_policy_enabled=True,
        test_policy_config={
            "require_tests_for_features": True,
            "require_tests_for_bug_fixes": True,
            "minimum_coverage_percent": 80.0,
            "allow_coverage_decrease": False,
            "max_coverage_decrease_percent": 0.0,
            "require_edge_case_tests": True,
            "require_integration_tests": False,
            "test_quality_threshold": 70.0,
            "auto_generate_tests": True,
            "test_frameworks": {
                "backend": "pytest",
                "frontend": "jest",
            },
        },
    )
    db_session.add(workspace)
    db_session.flush()

    # Add user as owner
    membership = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=test_user.id,
        role=WorkspaceMemberRole.OWNER.value,
        is_default=True,
    )
    db_session.add(membership)
    db_session.commit()
    db_session.refresh(workspace)
    return workspace


@pytest.fixture
def auth_headers(test_user):
    """Create authentication headers with mock token."""
    # In real tests, you'd generate a proper JWT token
    # For now, using a mock approach
    return {"Authorization": "Bearer mock_token"}


class TestGetTestPolicy:
    """Tests for GET /workspaces/{workspace_id}/test-policy."""

    def test_get_test_policy_success(self, client, test_workspace, auth_headers, mocker):
        """Test getting test policy successfully."""
        # Mock the authentication dependency
        mocker.patch("app.api.deps.get_current_user", return_value=test_workspace.owner)

        response = client.get(
            f"/api/v1/workspaces/{test_workspace.id}/test-policy",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["workspace_id"] == test_workspace.id
        assert data["test_policy_enabled"] is True
        assert data["test_policy_config"]["minimum_coverage_percent"] == 80.0

    def test_get_test_policy_workspace_not_found(self, client, auth_headers, mocker, test_user):
        """Test getting test policy for non-existent workspace."""
        mocker.patch("app.api.deps.get_current_user", return_value=test_user)

        response = client.get(
            "/api/v1/workspaces/99999/test-policy",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestUpdateTestPolicy:
    """Tests for PUT /workspaces/{workspace_id}/test-policy."""

    def test_update_test_policy_success(self, client, test_workspace, auth_headers, mocker):
        """Test updating test policy successfully."""
        mocker.patch("app.api.deps.get_current_user", return_value=test_workspace.owner)

        update_data = {
            "minimum_coverage_percent": 85.0,
            "test_quality_threshold": 75.0,
            "allow_coverage_decrease": True,
            "max_coverage_decrease_percent": 5.0,
        }

        response = client.put(
            f"/api/v1/workspaces/{test_workspace.id}/test-policy",
            headers=auth_headers,
            json=update_data,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["test_policy_config"]["minimum_coverage_percent"] == 85.0
        assert data["test_policy_config"]["test_quality_threshold"] == 75.0
        assert data["test_policy_config"]["allow_coverage_decrease"] is True
        assert data["test_policy_config"]["max_coverage_decrease_percent"] == 5.0

    def test_update_test_frameworks(self, client, test_workspace, auth_headers, mocker):
        """Test updating test frameworks configuration."""
        mocker.patch("app.api.deps.get_current_user", return_value=test_workspace.owner)

        update_data = {
            "test_frameworks": {
                "backend": "unittest",
                "frontend": "vitest",
            }
        }

        response = client.put(
            f"/api/v1/workspaces/{test_workspace.id}/test-policy",
            headers=auth_headers,
            json=update_data,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["test_policy_config"]["test_frameworks"]["backend"] == "unittest"
        assert data["test_policy_config"]["test_frameworks"]["frontend"] == "vitest"

    def test_update_test_policy_requires_admin(self, client, test_workspace, auth_headers, mocker, db_session):
        """Test that updating policy requires admin permission."""
        # Create a non-admin member
        regular_user = User(
            username="regularuser",
            email="regular@example.com",
            hashed_password="hashed",
            is_active=True,
        )
        db_session.add(regular_user)
        db_session.flush()

        membership = WorkspaceMember(
            workspace_id=test_workspace.id,
            user_id=regular_user.id,
            role=WorkspaceMemberRole.MEMBER.value,
        )
        db_session.add(membership)
        db_session.commit()

        mocker.patch("app.api.deps.get_current_user", return_value=regular_user)

        update_data = {"minimum_coverage_percent": 90.0}

        response = client.put(
            f"/api/v1/workspaces/{test_workspace.id}/test-policy",
            headers=auth_headers,
            json=update_data,
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestToggleTestPolicyEnabled:
    """Tests for PATCH /workspaces/{workspace_id}/test-policy/enabled."""

    def test_enable_test_policy(self, client, test_workspace, auth_headers, mocker, db_session):
        """Test enabling test policy."""
        # Disable first
        test_workspace.test_policy_enabled = False
        db_session.commit()

        mocker.patch("app.api.deps.get_current_user", return_value=test_workspace.owner)

        response = client.patch(
            f"/api/v1/workspaces/{test_workspace.id}/test-policy/enabled?enabled=true",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["test_policy_enabled"] is True

    def test_disable_test_policy(self, client, test_workspace, auth_headers, mocker):
        """Test disabling test policy."""
        mocker.patch("app.api.deps.get_current_user", return_value=test_workspace.owner)

        response = client.patch(
            f"/api/v1/workspaces/{test_workspace.id}/test-policy/enabled?enabled=false",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["test_policy_enabled"] is False

    def test_toggle_requires_admin(self, client, test_workspace, auth_headers, mocker, db_session):
        """Test that toggling policy requires admin permission."""
        # Create a non-admin member
        regular_user = User(
            username="regularuser2",
            email="regular2@example.com",
            hashed_password="hashed",
            is_active=True,
        )
        db_session.add(regular_user)
        db_session.flush()

        membership = WorkspaceMember(
            workspace_id=test_workspace.id,
            user_id=regular_user.id,
            role=WorkspaceMemberRole.MEMBER.value,
        )
        db_session.add(membership)
        db_session.commit()

        mocker.patch("app.api.deps.get_current_user", return_value=regular_user)

        response = client.patch(
            f"/api/v1/workspaces/{test_workspace.id}/test-policy/enabled?enabled=false",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
