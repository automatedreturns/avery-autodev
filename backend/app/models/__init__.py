"""Models package - imports all models for SQLAlchemy registration."""

from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember, WorkspaceMemberRole
from app.models.workspace_task import WorkspaceTask
from app.models.test_suite import TestSuite
from app.models.test_case import TestCase
from app.models.test_run import TestRun
from app.models.test_result import TestResult
from app.models.test_generation_job import TestGenerationJob
from app.models.magic_link import MagicLinkToken
from app.models.polling_history import PollingHistory
from app.models.polling_status import PollingStatus
from app.models.agent_message import AgentMessage
from app.models.agent_job import AgentJob
from app.models.ci_run import CIRun
# Phase 2: Test generation and coverage tracking
from app.models.agent_test_generation import AgentTestGeneration
from app.models.coverage_snapshot import CoverageSnapshot

__all__ = [
    "User",
    "Workspace",
    "WorkspaceMember",
    "WorkspaceMemberRole",
    "WorkspaceTask",
    "TestSuite",
    "TestCase",
    "TestRun",
    "TestResult",
    "TestGenerationJob",
    "MagicLinkToken",
    "PollingHistory",
    "PollingStatus",
    "AgentMessage",
    "AgentJob",
    "CIRun",
    # Phase 2 models
    "AgentTestGeneration",
    "CoverageSnapshot",
]
