"""Coverage Snapshot model - Phase 2: Tracks test coverage over time."""

from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey,
    JSON,
)
from sqlalchemy.orm import relationship

from app.database import Base


class CoverageSnapshot(Base):
    """Track test coverage snapshots over time."""

    __tablename__ = "coverage_snapshots"

    # Identity
    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    ci_run_id = Column(
        Integer,
        ForeignKey("ci_runs.id", ondelete="SET NULL"),
        nullable=True
    )
    agent_test_generation_id = Column(
        Integer,
        ForeignKey("agent_test_generations.id", ondelete="SET NULL"),
        nullable=True
    )

    # Line Coverage
    lines_covered = Column(Integer, nullable=False)
    lines_total = Column(Integer, nullable=False)
    coverage_percent = Column(Float, nullable=False)

    # Branch Coverage
    branches_covered = Column(Integer, nullable=True)
    branches_total = Column(Integer, nullable=True)
    branch_coverage_percent = Column(Float, nullable=True)

    # File-level Coverage
    # Structure: { "file.py": {"lines": 90.5, "branches": 85.0}, ... }
    file_coverage = Column(JSON, default=dict)

    # Uncovered Code
    # Structure: { "file.py": [10, 11, 25, 26, 27], ... }
    uncovered_lines = Column(JSON, default=dict)
    # List of function names without coverage
    uncovered_functions = Column(JSON, default=list)

    # Context
    commit_sha = Column(String(40), nullable=False)
    branch_name = Column(String(255), nullable=False)
    pr_number = Column(Integer, nullable=True)

    # Report Details
    report_format = Column(String(50))  # 'cobertura', 'lcov', 'json', 'xml'
    report_path = Column(String(500), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    workspace = relationship("Workspace", back_populates="coverage_snapshots")
    ci_run = relationship("CIRun", back_populates="coverage_snapshot", uselist=False)
    agent_test_generation = relationship(
        "AgentTestGeneration",
        back_populates="coverage_snapshot"
    )

    def __repr__(self):
        return (
            f"<CoverageSnapshot(id={self.id}, workspace_id={self.workspace_id}, "
            f"coverage={self.coverage_percent:.1f}%, commit={self.commit_sha[:7]})>"
        )

    def get_coverage_grade(self) -> str:
        """Get letter grade for coverage percentage."""
        if self.coverage_percent >= 90:
            return "A"
        elif self.coverage_percent >= 80:
            return "B"
        elif self.coverage_percent >= 70:
            return "C"
        elif self.coverage_percent >= 60:
            return "D"
        else:
            return "F"

    def calculate_delta(self, previous_snapshot: 'CoverageSnapshot') -> dict:
        """Calculate coverage delta compared to previous snapshot."""
        if not previous_snapshot:
            return {
                "delta_percent": 0.0,
                "delta_lines": 0,
                "improved": False
            }

        delta_percent = self.coverage_percent - previous_snapshot.coverage_percent
        delta_lines = self.lines_covered - previous_snapshot.lines_covered

        return {
            "delta_percent": delta_percent,
            "delta_lines": delta_lines,
            "improved": delta_percent > 0
        }

    def get_uncovered_count(self) -> int:
        """Get total number of uncovered lines."""
        total = 0
        for lines in self.uncovered_lines.values():
            total += len(lines)
        return total

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "ci_run_id": self.ci_run_id,
            "agent_test_generation_id": self.agent_test_generation_id,
            "lines_covered": self.lines_covered,
            "lines_total": self.lines_total,
            "coverage_percent": self.coverage_percent,
            "branches_covered": self.branches_covered,
            "branches_total": self.branches_total,
            "branch_coverage_percent": self.branch_coverage_percent,
            "file_coverage": self.file_coverage,
            "uncovered_lines": self.uncovered_lines,
            "uncovered_functions": self.uncovered_functions,
            "commit_sha": self.commit_sha,
            "branch_name": self.branch_name,
            "pr_number": self.pr_number,
            "report_format": self.report_format,
            "report_path": self.report_path,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "coverage_grade": self.get_coverage_grade(),
            "uncovered_count": self.get_uncovered_count()
        }
