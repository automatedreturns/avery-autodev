"""Workspace model for managing developer workspaces with Git provider integration."""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, JSON
from sqlalchemy.orm import relationship

from app.database import Base


class Workspace(Base):
    """Workspace model for database."""

    __tablename__ = "workspaces"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)

    # Git Provider Configuration
    git_provider = Column(String, nullable=False, default="github")  # "github" or "gitlab"
    gitlab_url = Column(String, nullable=True)  # For self-hosted GitLab (default: https://gitlab.com)

    # Repository Integration (provider-agnostic)
    github_repository = Column(String, nullable=False)  # Format: "owner/repo" or "namespace/project"
    github_dev_branch = Column(String, nullable=False)  # Development branch name
    github_main_branch = Column(String, nullable=False, default="main")  # Production branch
    local_repo_path = Column(String, nullable=True)  # Local path where repository is cloned

    # Status
    is_active = Column(Boolean, default=True)

    # Ownership
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_issue_poll = Column(DateTime, nullable=True)  # Last time issues were polled

    # Polling configuration
    polling_enabled = Column(Boolean, default=False, nullable=False)  # Enable/disable automatic polling

    # CI Self-Fix Configuration
    auto_create_issues = Column(Boolean, default=True, nullable=False)  # Automatically create GitHub issues for failed CI runs

    # Phase 2: Test Policy Configuration
    test_policy_enabled = Column(Boolean, default=True, nullable=False)
    test_policy_config = Column(JSON, default=lambda: {
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
            "frontend": "jest"
        }
    })

    # Relationships
    owner = relationship("User", back_populates="owned_workspaces", foreign_keys=[owner_id])
    members = relationship("WorkspaceMember", back_populates="workspace", cascade="all, delete-orphan")
    tasks = relationship("WorkspaceTask", back_populates="workspace", cascade="all, delete-orphan")
    test_suites = relationship("TestSuite", back_populates="workspace", cascade="all, delete-orphan")
    test_generation_jobs = relationship("TestGenerationJob", back_populates="workspace", cascade="all, delete-orphan")
    ci_runs = relationship("CIRun", back_populates="workspace", cascade="all, delete-orphan")
    # Phase 2 relationships
    agent_test_generations = relationship("AgentTestGeneration", back_populates="workspace", cascade="all, delete-orphan")
    coverage_snapshots = relationship("CoverageSnapshot", back_populates="workspace", cascade="all, delete-orphan")
