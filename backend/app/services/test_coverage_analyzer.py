"""
Phase 2: Test Coverage Analyzer Service

Analyzes test coverage reports, tracks coverage trends over time, and integrates
with the coverage_snapshots database model. Extends the basic coverage_service.py
with database integration and advanced analysis features.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.coverage_snapshot import CoverageSnapshot
from app.models.workspace import Workspace
from app.services.coverage_service import (
    CoverageParseError,
    parse_coverage_report,
    get_coverage_diff,
)

logger = logging.getLogger(__name__)


@dataclass
class CoverageReport:
    """Parsed coverage report data."""

    coverage_percent: float
    lines_covered: int
    lines_total: int
    branches_covered: Optional[int] = None
    branches_total: Optional[int] = None
    branch_coverage_percent: Optional[float] = None
    file_coverage: dict[str, dict] = None  # {"file.py": {"lines": 90.5, "branches": 85.0}}
    uncovered_lines: dict[str, list[int]] = None  # {"file.py": [10, 11, 25]}
    uncovered_functions: list[str] = None  # ["function_name", ...]

    def __post_init__(self):
        """Initialize optional fields."""
        if self.file_coverage is None:
            self.file_coverage = {}
        if self.uncovered_lines is None:
            self.uncovered_lines = {}
        if self.uncovered_functions is None:
            self.uncovered_functions = []


@dataclass
class CoverageDelta:
    """Coverage change between two snapshots."""

    delta_percent: float
    delta_lines: int
    previous_coverage: float
    current_coverage: float
    improved: bool
    improved_files: list[dict]
    regressed_files: list[dict]


@dataclass
class CoverageTrend:
    """Coverage trend over time."""

    snapshots: list[CoverageSnapshot]
    trend_direction: str  # 'improving', 'declining', 'stable'
    average_coverage: float
    min_coverage: float
    max_coverage: float
    total_change: float
    days_tracked: int


class TestCoverageAnalyzer:
    """
    Phase 2: Analyzes test coverage reports and tracks trends over time.

    This service:
    1. Parses coverage reports (pytest-cov, jest, istanbul)
    2. Stores coverage snapshots in the database
    3. Calculates coverage deltas between runs
    4. Identifies uncovered code for targeted test generation
    5. Analyzes coverage trends over time
    """

    def __init__(self, db: Session):
        """
        Initialize the coverage analyzer.

        Args:
            db: Database session
        """
        self.db = db

    def parse_and_store_coverage(
        self,
        workspace_id: int,
        repo_path: str,
        framework: str,
        commit_sha: str,
        branch_name: str,
        ci_run_id: Optional[int] = None,
        agent_test_generation_id: Optional[int] = None,
        pr_number: Optional[int] = None,
    ) -> CoverageSnapshot:
        """
        Parse coverage report and store snapshot in database.

        Args:
            workspace_id: Workspace ID
            repo_path: Path to repository
            framework: Test framework (pytest, jest, mocha)
            commit_sha: Git commit SHA
            branch_name: Git branch name
            ci_run_id: Optional CI run ID
            agent_test_generation_id: Optional test generation ID
            pr_number: Optional PR number

        Returns:
            Created CoverageSnapshot

        Raises:
            CoverageParseError: If parsing fails
        """
        # Parse coverage report using existing service
        coverage_data = parse_coverage_report(repo_path, framework)

        if coverage_data["coverage_percentage"] is None:
            raise CoverageParseError("No coverage data found")

        # Transform to CoverageReport dataclass
        coverage_report = self._transform_coverage_data(coverage_data)

        # Create snapshot
        snapshot = CoverageSnapshot(
            workspace_id=workspace_id,
            ci_run_id=ci_run_id,
            agent_test_generation_id=agent_test_generation_id,
            lines_covered=coverage_report.lines_covered,
            lines_total=coverage_report.lines_total,
            coverage_percent=coverage_report.coverage_percent,
            branches_covered=coverage_report.branches_covered,
            branches_total=coverage_report.branches_total,
            branch_coverage_percent=coverage_report.branch_coverage_percent,
            file_coverage=coverage_report.file_coverage,
            uncovered_lines=coverage_report.uncovered_lines,
            uncovered_functions=coverage_report.uncovered_functions,
            commit_sha=commit_sha,
            branch_name=branch_name,
            pr_number=pr_number,
            report_format=framework,
            report_path=repo_path,
        )

        self.db.add(snapshot)
        self.db.commit()
        self.db.refresh(snapshot)

        logger.info(
            f"Stored coverage snapshot {snapshot.id} for workspace {workspace_id}: "
            f"{coverage_report.coverage_percent}% coverage"
        )

        return snapshot

    def create_snapshot(
        self,
        workspace_id: int,
        coverage_data: dict,
        commit_sha: str,
        branch_name: str,
        pr_number: Optional[int] = None,
        ci_run_id: Optional[int] = None,
        agent_test_generation_id: Optional[int] = None,
        report_format: Optional[str] = None,
    ) -> CoverageSnapshot:
        """
        Create a coverage snapshot from pre-parsed coverage data.

        This method is used by the CI webhook to store coverage data that has
        already been parsed from GitHub Actions coverage reports.

        Args:
            workspace_id: Workspace ID
            coverage_data: Dict containing coverage metrics:
                - coverage_percent: Overall coverage percentage
                - lines_covered: Number of lines covered
                - lines_total: Total number of lines
                - file_coverage: Dict mapping file paths to coverage data
                - uncovered_lines: Dict mapping file paths to uncovered line numbers
                - uncovered_functions: List of uncovered function names
            commit_sha: Git commit SHA
            branch_name: Git branch name
            pr_number: Optional PR number
            ci_run_id: Optional CI run ID
            agent_test_generation_id: Optional test generation ID
            report_format: Optional report format (e.g., 'coverage.py', 'jest')

        Returns:
            Created CoverageSnapshot
        """
        # Extract coverage metrics with defaults
        coverage_percent = coverage_data.get("coverage_percent", 0.0)
        lines_covered = coverage_data.get("lines_covered", 0)
        lines_total = coverage_data.get("lines_total", 0)
        file_coverage = coverage_data.get("file_coverage", {})
        uncovered_lines = coverage_data.get("uncovered_lines", {})
        uncovered_functions = coverage_data.get("uncovered_functions", [])

        # Create snapshot
        snapshot = CoverageSnapshot(
            workspace_id=workspace_id,
            ci_run_id=ci_run_id,
            agent_test_generation_id=agent_test_generation_id,
            lines_covered=lines_covered,
            lines_total=lines_total,
            coverage_percent=coverage_percent,
            file_coverage=file_coverage,
            uncovered_lines=uncovered_lines,
            uncovered_functions=uncovered_functions,
            commit_sha=commit_sha,
            branch_name=branch_name,
            pr_number=pr_number,
            report_format=report_format,
        )

        self.db.add(snapshot)
        self.db.commit()
        self.db.refresh(snapshot)

        logger.info(
            f"Created coverage snapshot {snapshot.id} for workspace {workspace_id}: "
            f"{coverage_percent}% coverage ({lines_covered}/{lines_total} lines)"
        )

        return snapshot

    def store_coverage_snapshot(
        self,
        workspace_id: int,
        coverage_percent: float,
        lines_covered: int,
        lines_total: int,
        commit_sha: str,
        branch_name: str,
        branches_covered: Optional[int] = None,
        branches_total: Optional[int] = None,
        branch_coverage_percent: Optional[float] = None,
        file_coverage: Optional[dict] = None,
        uncovered_lines: Optional[dict] = None,
        uncovered_functions: Optional[list] = None,
        pr_number: Optional[int] = None,
        report_format: Optional[str] = None,
        report_path: Optional[str] = None,
        ci_run_id: Optional[int] = None,
        agent_test_generation_id: Optional[int] = None,
    ) -> CoverageSnapshot:
        """
        Store a coverage snapshot with explicit parameters.

        This method is used by the coverage API endpoint to store coverage
        snapshots with all fields explicitly provided.

        Args:
            workspace_id: Workspace ID
            coverage_percent: Overall coverage percentage
            lines_covered: Number of lines covered
            lines_total: Total number of lines
            commit_sha: Git commit SHA
            branch_name: Git branch name
            branches_covered: Optional number of branches covered
            branches_total: Optional total number of branches
            branch_coverage_percent: Optional branch coverage percentage
            file_coverage: Optional dict mapping file paths to coverage data
            uncovered_lines: Optional dict mapping file paths to uncovered line numbers
            uncovered_functions: Optional list of uncovered function names
            pr_number: Optional PR number
            report_format: Optional report format
            report_path: Optional path to coverage report
            ci_run_id: Optional CI run ID
            agent_test_generation_id: Optional test generation ID

        Returns:
            Created CoverageSnapshot
        """
        snapshot = CoverageSnapshot(
            workspace_id=workspace_id,
            ci_run_id=ci_run_id,
            agent_test_generation_id=agent_test_generation_id,
            lines_covered=lines_covered,
            lines_total=lines_total,
            coverage_percent=coverage_percent,
            branches_covered=branches_covered,
            branches_total=branches_total,
            branch_coverage_percent=branch_coverage_percent,
            file_coverage=file_coverage or {},
            uncovered_lines=uncovered_lines or {},
            uncovered_functions=uncovered_functions or [],
            commit_sha=commit_sha,
            branch_name=branch_name,
            pr_number=pr_number,
            report_format=report_format,
            report_path=report_path,
        )

        self.db.add(snapshot)
        self.db.commit()
        self.db.refresh(snapshot)

        logger.info(
            f"Stored coverage snapshot {snapshot.id} for workspace {workspace_id}: "
            f"{coverage_percent}% coverage ({lines_covered}/{lines_total} lines)"
        )

        return snapshot

    def calculate_coverage_delta(
        self,
        current_snapshot_id: int,
        previous_snapshot_id: Optional[int] = None,
    ) -> Optional[CoverageDelta]:
        """
        Calculate coverage delta between two snapshots.

        Args:
            current_snapshot_id: Current snapshot ID
            previous_snapshot_id: Previous snapshot ID (or latest if None)

        Returns:
            CoverageDelta or None if no previous snapshot
        """
        current = self.db.query(CoverageSnapshot).filter(
            CoverageSnapshot.id == current_snapshot_id
        ).first()

        if not current:
            logger.error(f"Current snapshot {current_snapshot_id} not found")
            return None

        # Get previous snapshot
        if previous_snapshot_id:
            previous = self.db.query(CoverageSnapshot).filter(
                CoverageSnapshot.id == previous_snapshot_id
            ).first()
        else:
            # Get most recent snapshot before current
            previous = (
                self.db.query(CoverageSnapshot)
                .filter(
                    CoverageSnapshot.workspace_id == current.workspace_id,
                    CoverageSnapshot.id < current.id,
                )
                .order_by(CoverageSnapshot.created_at.desc())
                .first()
            )

        if not previous:
            logger.info(f"No previous snapshot found for comparison")
            return None

        # Calculate delta using model method
        delta_data = current.calculate_delta(previous)

        # Calculate file-level changes
        improved_files = []
        regressed_files = []

        current_files = current.file_coverage or {}
        previous_files = previous.file_coverage or {}

        for file_path, current_data in current_files.items():
            if file_path in previous_files:
                current_cov = current_data.get("lines", 0)
                previous_cov = previous_files[file_path].get("lines", 0)
                file_delta = current_cov - previous_cov

                if file_delta > 0.1:  # Improved by >0.1%
                    improved_files.append({
                        "path": file_path,
                        "delta": round(file_delta, 2),
                        "current": round(current_cov, 2),
                        "previous": round(previous_cov, 2),
                    })
                elif file_delta < -0.1:  # Regressed by >0.1%
                    regressed_files.append({
                        "path": file_path,
                        "delta": round(file_delta, 2),
                        "current": round(current_cov, 2),
                        "previous": round(previous_cov, 2),
                    })

        # Sort by absolute delta
        improved_files.sort(key=lambda x: abs(x["delta"]), reverse=True)
        regressed_files.sort(key=lambda x: abs(x["delta"]), reverse=True)

        return CoverageDelta(
            delta_percent=delta_data["delta_percent"],
            delta_lines=delta_data["delta_lines"],
            previous_coverage=previous.coverage_percent,
            current_coverage=current.coverage_percent,
            improved=delta_data["improved"],
            improved_files=improved_files[:10],  # Top 10
            regressed_files=regressed_files[:10],  # Top 10
        )

    def identify_uncovered_code(
        self,
        snapshot_id: int,
        max_files: int = 10,
        max_lines_per_file: int = 20,
    ) -> dict[str, Any]:
        """
        Identify uncovered code that needs test coverage.

        Prioritizes files with:
        1. Most uncovered lines
        2. Lowest coverage percentage
        3. Critical files (configurable)

        Args:
            snapshot_id: Coverage snapshot ID
            max_files: Maximum files to return
            max_lines_per_file: Maximum lines per file

        Returns:
            Dictionary with prioritized uncovered code
        """
        snapshot = self.db.query(CoverageSnapshot).filter(
            CoverageSnapshot.id == snapshot_id
        ).first()

        if not snapshot:
            logger.error(f"Snapshot {snapshot_id} not found")
            return {}

        uncovered_lines = snapshot.uncovered_lines or {}
        file_coverage = snapshot.file_coverage or {}

        # Build priority list
        priority_files = []
        for file_path, line_numbers in uncovered_lines.items():
            if not line_numbers:
                continue

            file_cov_data = file_coverage.get(file_path, {})
            file_coverage_pct = file_cov_data.get("lines", 0)

            priority_files.append({
                "path": file_path,
                "uncovered_count": len(line_numbers),
                "uncovered_lines": line_numbers[:max_lines_per_file],
                "coverage": file_coverage_pct,
                "priority_score": len(line_numbers) * (100 - file_coverage_pct),
            })

        # Sort by priority score (more uncovered lines + lower coverage = higher priority)
        priority_files.sort(key=lambda x: x["priority_score"], reverse=True)

        total_uncovered = sum(f["uncovered_count"] for f in priority_files)

        return {
            "snapshot_id": snapshot_id,
            "total_uncovered_lines": total_uncovered,
            "files_with_gaps": len(priority_files),
            "priority_files": priority_files[:max_files],
            "coverage_percent": snapshot.coverage_percent,
            "coverage_grade": snapshot.get_coverage_grade(),
        }

    def get_coverage_trend(
        self,
        workspace_id: int,
        days: int = 30,
        branch_name: Optional[str] = None,
    ) -> Optional[CoverageTrend]:
        """
        Analyze coverage trend over time.

        Args:
            workspace_id: Workspace ID
            days: Number of days to analyze
            branch_name: Optional branch filter

        Returns:
            CoverageTrend or None if insufficient data
        """
        since_date = datetime.utcnow() - timedelta(days=days)

        query = self.db.query(CoverageSnapshot).filter(
            CoverageSnapshot.workspace_id == workspace_id,
            CoverageSnapshot.created_at >= since_date,
        )

        if branch_name:
            query = query.filter(CoverageSnapshot.branch_name == branch_name)

        snapshots = query.order_by(CoverageSnapshot.created_at.asc()).all()

        if len(snapshots) < 2:
            logger.info(f"Insufficient data for trend analysis (need 2+ snapshots)")
            return None

        # Calculate metrics
        coverage_values = [s.coverage_percent for s in snapshots]
        average_coverage = sum(coverage_values) / len(coverage_values)
        min_coverage = min(coverage_values)
        max_coverage = max(coverage_values)
        total_change = coverage_values[-1] - coverage_values[0]

        # Determine trend direction
        # Use linear regression or simple comparison
        if total_change > 1.0:
            trend_direction = "improving"
        elif total_change < -1.0:
            trend_direction = "declining"
        else:
            trend_direction = "stable"

        return CoverageTrend(
            snapshots=snapshots,
            trend_direction=trend_direction,
            average_coverage=round(average_coverage, 2),
            min_coverage=round(min_coverage, 2),
            max_coverage=round(max_coverage, 2),
            total_change=round(total_change, 2),
            days_tracked=days,
        )

    def get_latest_snapshot(
        self,
        workspace_id: int,
        branch_name: Optional[str] = None,
    ) -> Optional[CoverageSnapshot]:
        """
        Get the most recent coverage snapshot.

        Args:
            workspace_id: Workspace ID
            branch_name: Optional branch filter

        Returns:
            Latest CoverageSnapshot or None
        """
        query = self.db.query(CoverageSnapshot).filter(
            CoverageSnapshot.workspace_id == workspace_id
        )

        if branch_name:
            query = query.filter(CoverageSnapshot.branch_name == branch_name)

        return query.order_by(CoverageSnapshot.created_at.desc()).first()

    def compare_snapshots(
        self,
        snapshot_id_1: int,
        snapshot_id_2: int,
    ) -> dict[str, Any]:
        """
        Compare two coverage snapshots in detail.

        Args:
            snapshot_id_1: First snapshot ID
            snapshot_id_2: Second snapshot ID

        Returns:
            Detailed comparison dictionary
        """
        snapshot1 = self.db.query(CoverageSnapshot).filter(
            CoverageSnapshot.id == snapshot_id_1
        ).first()
        snapshot2 = self.db.query(CoverageSnapshot).filter(
            CoverageSnapshot.id == snapshot_id_2
        ).first()

        if not snapshot1 or not snapshot2:
            logger.error("One or both snapshots not found")
            return {}

        # Overall comparison
        coverage_delta = snapshot2.coverage_percent - snapshot1.coverage_percent
        lines_delta = snapshot2.lines_covered - snapshot1.lines_covered

        # File-level comparison
        files1 = snapshot1.file_coverage or {}
        files2 = snapshot2.file_coverage or {}

        all_files = set(files1.keys()) | set(files2.keys())
        file_changes = []

        for file_path in all_files:
            cov1 = files1.get(file_path, {}).get("lines", 0) if file_path in files1 else 0
            cov2 = files2.get(file_path, {}).get("lines", 0) if file_path in files2 else 0
            delta = cov2 - cov1

            if abs(delta) > 0.1:  # Changed by more than 0.1%
                file_changes.append({
                    "path": file_path,
                    "snapshot1_coverage": round(cov1, 2),
                    "snapshot2_coverage": round(cov2, 2),
                    "delta": round(delta, 2),
                    "status": "improved" if delta > 0 else "regressed",
                })

        file_changes.sort(key=lambda x: abs(x["delta"]), reverse=True)

        return {
            "snapshot1": {
                "id": snapshot1.id,
                "coverage": snapshot1.coverage_percent,
                "commit": snapshot1.commit_sha,
                "date": snapshot1.created_at.isoformat(),
            },
            "snapshot2": {
                "id": snapshot2.id,
                "coverage": snapshot2.coverage_percent,
                "commit": snapshot2.commit_sha,
                "date": snapshot2.created_at.isoformat(),
            },
            "overall_delta": round(coverage_delta, 2),
            "lines_delta": lines_delta,
            "status": "improved" if coverage_delta > 0 else "regressed" if coverage_delta < 0 else "unchanged",
            "file_changes": file_changes[:20],  # Top 20
            "total_files_changed": len(file_changes),
        }

    def _transform_coverage_data(self, coverage_data: dict[str, Any]) -> CoverageReport:
        """
        Transform parsed coverage data to CoverageReport dataclass.

        Args:
            coverage_data: Raw parsed coverage data

        Returns:
            CoverageReport instance
        """
        # Build file_coverage dict
        file_coverage = {}
        uncovered_lines = {}

        for file_data in coverage_data.get("files", []):
            file_path = file_data["path"]
            file_coverage[file_path] = {
                "lines": file_data.get("coverage", 0),
                "lines_covered": file_data.get("lines_covered", 0),
                "lines_total": file_data.get("lines_total", 0),
            }
            uncovered_lines[file_path] = file_data.get("uncovered_lines", [])

        return CoverageReport(
            coverage_percent=coverage_data.get("coverage_percentage", 0),
            lines_covered=coverage_data.get("lines_covered", 0),
            lines_total=coverage_data.get("lines_total", 0),
            file_coverage=file_coverage,
            uncovered_lines=uncovered_lines,
        )
