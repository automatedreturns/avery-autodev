"""
Pytest configuration and fixtures for Phase 2 tests.
"""

import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.workspace import Workspace
from app.models.coverage_snapshot import CoverageSnapshot
from app.models.agent_test_generation import AgentTestGeneration
from app.models.agent_job import AgentJob
from app.models.ci_run import CIRun


@pytest.fixture(scope="function")
def db_session():
    """
    Create an in-memory SQLite database for testing.
    Each test gets a fresh database.
    """
    # Create in-memory SQLite database
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Create all tables
    Base.metadata.create_all(bind=engine)

    # Create session
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    yield session

    # Cleanup
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def sample_workspace(db_session: Session):
    """Create a sample workspace for testing."""
    # Create a test user first (required by Workspace)
    from app.models.user import User
    user = User(
        id=1,
        email="test@example.com",
        username="testuser",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    workspace = Workspace(
        id=1,
        name="Test Workspace",
        github_repository="test/repo",
        github_dev_branch="dev",
        github_main_branch="main",
        owner_id=user.id,
        test_policy_enabled=True,
        test_policy_config={
            "require_tests_for_features": True,
            "require_tests_for_bug_fixes": True,
            "minimum_coverage_percent": 80.0,
            "allow_coverage_decrease": False,
            "test_quality_threshold": 70.0,
            "auto_generate_tests": True,
            "test_frameworks": {
                "backend": "pytest",
                "frontend": "jest"
            }
        }
    )
    db_session.add(workspace)
    db_session.commit()
    db_session.refresh(workspace)
    return workspace


@pytest.fixture
def sample_coverage_snapshot(db_session: Session, sample_workspace: Workspace):
    """Create a sample coverage snapshot."""
    snapshot = CoverageSnapshot(
        workspace_id=sample_workspace.id,
        lines_covered=900,
        lines_total=1000,
        coverage_percent=90.0,
        branches_covered=80,
        branches_total=100,
        branch_coverage_percent=80.0,
        file_coverage={
            "app/services/auth.py": {
                "lines": 95.5,
                "lines_covered": 95,
                "lines_total": 100
            },
            "app/services/user.py": {
                "lines": 85.0,
                "lines_covered": 85,
                "lines_total": 100
            }
        },
        uncovered_lines={
            "app/services/auth.py": [15, 16, 23, 45],
            "app/services/user.py": [10, 11, 25, 26, 27, 89, 102, 115, 120, 127, 130, 145, 150, 160, 165]
        },
        uncovered_functions=["handle_edge_case", "validate_input"],
        commit_sha="abc123def456",
        branch_name="main",
        pr_number=None,
        report_format="pytest",
        report_path="/tmp/repo",
    )
    db_session.add(snapshot)
    db_session.commit()
    db_session.refresh(snapshot)
    return snapshot


@pytest.fixture
def sample_coverage_snapshots_trend(db_session: Session, sample_workspace: Workspace):
    """Create multiple snapshots for trend analysis."""
    snapshots = []
    base_coverage = 75.0

    for i in range(5):
        snapshot = CoverageSnapshot(
            workspace_id=sample_workspace.id,
            lines_covered=750 + (i * 50),
            lines_total=1000,
            coverage_percent=base_coverage + (i * 2.5),  # Increasing trend
            commit_sha=f"commit{i}",
            branch_name="main",
            report_format="pytest",
            report_path="/tmp/repo",
        )
        db_session.add(snapshot)
        snapshots.append(snapshot)

    db_session.commit()
    for snapshot in snapshots:
        db_session.refresh(snapshot)

    return snapshots


@pytest.fixture
def sample_coverage_data():
    """Sample parsed coverage data (from coverage_service.py)."""
    return {
        "coverage_percentage": 85.5,
        "lines_covered": 855,
        "lines_total": 1000,
        "files": [
            {
                "path": "app/services/foo.py",
                "coverage": 92.3,
                "lines_covered": 120,
                "lines_total": 130,
                "uncovered_lines": [15, 16, 23, 45, 67, 89, 102, 115, 120, 127]
            },
            {
                "path": "app/services/bar.py",
                "coverage": 78.0,
                "lines_covered": 78,
                "lines_total": 100,
                "uncovered_lines": [10, 11, 25, 26, 27, 89, 102, 115, 120, 127, 130, 145, 150, 160, 165, 170, 180, 190, 195, 200, 210, 220]
            }
        ]
    }


@pytest.fixture
def sample_agent_job(db_session: Session, sample_workspace: Workspace):
    """Create a sample agent job."""
    # Create a workspace_task first (required by AgentJob)
    from app.models.workspace_task import WorkspaceTask
    task = WorkspaceTask(
        workspace_id=sample_workspace.id,
        github_issue_number=123,
        github_issue_title="Test Task",
        added_by_user_id=sample_workspace.owner_id,
        agent_status="completed",
    )
    db_session.add(task)
    db_session.commit()

    job = AgentJob(
        workspace_id=sample_workspace.id,
        task_id=task.id,
        celery_task_id="test-celery-id-123",
        status="completed",
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


@pytest.fixture
def sample_ci_run(db_session: Session, sample_workspace: Workspace, sample_agent_job: AgentJob):
    """Create a sample CI run."""
    ci_run = CIRun(
        workspace_id=sample_workspace.id,
        agent_job_id=sample_agent_job.id,
        repository=sample_workspace.github_repository,
        pr_number=456,
        run_id="123456789",
        job_name="test-job",
        status="success",
        commit_sha="abc123",
        branch_name="main",
    )
    db_session.add(ci_run)
    db_session.commit()
    db_session.refresh(ci_run)
    return ci_run
