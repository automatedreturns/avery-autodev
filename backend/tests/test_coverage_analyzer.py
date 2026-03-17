"""
Unit tests for Phase 2 TestCoverageAnalyzer service.

Tests coverage:
- Coverage report parsing and storage
- Coverage delta calculation
- Uncovered code identification
- Coverage trend analysis
- Snapshot comparison
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from app.services.test_coverage_analyzer import (
    TestCoverageAnalyzer,
    CoverageReport,
    CoverageDelta,
    CoverageTrend,
)
from app.services.coverage_service import CoverageParseError
from app.models.coverage_snapshot import CoverageSnapshot
from app.models.workspace import Workspace


class TestCoverageReportDataclass:
    """Test CoverageReport dataclass."""

    def test_coverage_report_creation(self):
        """Test creating a CoverageReport instance."""
        report = CoverageReport(
            coverage_percent=85.5,
            lines_covered=855,
            lines_total=1000,
        )
        assert report.coverage_percent == 85.5
        assert report.lines_covered == 855
        assert report.lines_total == 1000
        assert report.file_coverage == {}
        assert report.uncovered_lines == {}
        assert report.uncovered_functions == []

    def test_coverage_report_with_optional_fields(self):
        """Test CoverageReport with all fields."""
        report = CoverageReport(
            coverage_percent=90.0,
            lines_covered=900,
            lines_total=1000,
            branches_covered=80,
            branches_total=100,
            branch_coverage_percent=80.0,
            file_coverage={"file.py": {"lines": 95.0}},
            uncovered_lines={"file.py": [10, 20, 30]},
            uncovered_functions=["func1", "func2"],
        )
        assert report.branches_covered == 80
        assert report.branch_coverage_percent == 80.0
        assert "file.py" in report.file_coverage
        assert report.uncovered_lines["file.py"] == [10, 20, 30]
        assert len(report.uncovered_functions) == 2


class TestParseAndStoreCoverage:
    """Test parse_and_store_coverage method."""

    @patch('app.services.test_coverage_analyzer.parse_coverage_report')
    def test_parse_and_store_success(
        self,
        mock_parse,
        db_session,
        sample_workspace,
        sample_coverage_data
    ):
        """Test successful coverage parsing and storage."""
        # Mock parse_coverage_report
        mock_parse.return_value = sample_coverage_data

        analyzer = TestCoverageAnalyzer(db_session)
        snapshot = analyzer.parse_and_store_coverage(
            workspace_id=sample_workspace.id,
            repo_path="/tmp/repo",
            framework="pytest",
            commit_sha="abc123",
            branch_name="main",
        )

        # Verify snapshot was created
        assert snapshot.id is not None
        assert snapshot.workspace_id == sample_workspace.id
        assert snapshot.coverage_percent == 85.5
        assert snapshot.lines_covered == 855
        assert snapshot.lines_total == 1000
        assert snapshot.commit_sha == "abc123"
        assert snapshot.branch_name == "main"
        assert snapshot.report_format == "pytest"

        # Verify file_coverage was stored
        assert "app/services/foo.py" in snapshot.file_coverage
        assert snapshot.file_coverage["app/services/foo.py"]["lines"] == 92.3

        # Verify uncovered_lines was stored
        assert "app/services/foo.py" in snapshot.uncovered_lines
        assert 15 in snapshot.uncovered_lines["app/services/foo.py"]

    @patch('app.services.test_coverage_analyzer.parse_coverage_report')
    def test_parse_and_store_with_ci_run(
        self,
        mock_parse,
        db_session,
        sample_workspace,
        sample_ci_run,
        sample_coverage_data
    ):
        """Test storing coverage with CI run association."""
        mock_parse.return_value = sample_coverage_data

        analyzer = TestCoverageAnalyzer(db_session)
        snapshot = analyzer.parse_and_store_coverage(
            workspace_id=sample_workspace.id,
            repo_path="/tmp/repo",
            framework="pytest",
            commit_sha="abc123",
            branch_name="main",
            ci_run_id=sample_ci_run.id,
        )

        assert snapshot.ci_run_id == sample_ci_run.id

    @patch('app.services.test_coverage_analyzer.parse_coverage_report')
    def test_parse_and_store_no_coverage_data(
        self,
        mock_parse,
        db_session,
        sample_workspace
    ):
        """Test parsing when no coverage data is found."""
        mock_parse.return_value = {
            "coverage_percentage": None,
            "lines_covered": 0,
            "lines_total": 0,
            "files": []
        }

        analyzer = TestCoverageAnalyzer(db_session)

        with pytest.raises(CoverageParseError, match="No coverage data found"):
            analyzer.parse_and_store_coverage(
                workspace_id=sample_workspace.id,
                repo_path="/tmp/repo",
                framework="pytest",
                commit_sha="abc123",
                branch_name="main",
            )

    @patch('app.services.test_coverage_analyzer.parse_coverage_report')
    def test_parse_and_store_parse_error(
        self,
        mock_parse,
        db_session,
        sample_workspace
    ):
        """Test handling parse errors."""
        mock_parse.side_effect = CoverageParseError("Failed to parse")

        analyzer = TestCoverageAnalyzer(db_session)

        with pytest.raises(CoverageParseError):
            analyzer.parse_and_store_coverage(
                workspace_id=sample_workspace.id,
                repo_path="/tmp/repo",
                framework="pytest",
                commit_sha="abc123",
                branch_name="main",
            )


class TestCalculateCoverageDelta:
    """Test calculate_coverage_delta method."""

    def test_calculate_delta_with_previous_snapshot(
        self,
        db_session,
        sample_workspace
    ):
        """Test delta calculation between two snapshots."""
        analyzer = TestCoverageAnalyzer(db_session)

        # Create previous snapshot
        previous = CoverageSnapshot(
            workspace_id=sample_workspace.id,
            lines_covered=800,
            lines_total=1000,
            coverage_percent=80.0,
            file_coverage={
                "app/foo.py": {"lines": 75.0},
                "app/bar.py": {"lines": 85.0},
            },
            commit_sha="prev123",
            branch_name="main",
            report_format="pytest",
            report_path="/tmp/repo",
        )
        db_session.add(previous)
        db_session.commit()
        db_session.refresh(previous)

        # Create current snapshot
        current = CoverageSnapshot(
            workspace_id=sample_workspace.id,
            lines_covered=900,
            lines_total=1000,
            coverage_percent=90.0,
            file_coverage={
                "app/foo.py": {"lines": 95.0},  # Improved by 20%
                "app/bar.py": {"lines": 85.0},  # Unchanged
            },
            commit_sha="curr123",
            branch_name="main",
            report_format="pytest",
            report_path="/tmp/repo",
        )
        db_session.add(current)
        db_session.commit()
        db_session.refresh(current)

        # Calculate delta
        delta = analyzer.calculate_coverage_delta(current.id, previous.id)

        assert delta is not None
        assert delta.delta_percent == 10.0
        assert delta.delta_lines == 100
        assert delta.previous_coverage == 80.0
        assert delta.current_coverage == 90.0
        assert delta.improved is True

        # Check file-level changes
        assert len(delta.improved_files) == 1
        assert delta.improved_files[0]["path"] == "app/foo.py"
        assert delta.improved_files[0]["delta"] == 20.0

    def test_calculate_delta_auto_previous(
        self,
        db_session,
        sample_coverage_snapshots_trend
    ):
        """Test delta calculation with automatic previous snapshot selection."""
        analyzer = TestCoverageAnalyzer(db_session)

        # Get latest snapshot
        latest = sample_coverage_snapshots_trend[-1]

        # Calculate delta (should compare with second-to-last)
        delta = analyzer.calculate_coverage_delta(latest.id)

        assert delta is not None
        assert delta.improved is True
        assert delta.delta_percent == 2.5  # Each snapshot increases by 2.5%

    def test_calculate_delta_no_previous(
        self,
        db_session,
        sample_coverage_snapshot
    ):
        """Test delta calculation when no previous snapshot exists."""
        analyzer = TestCoverageAnalyzer(db_session)

        delta = analyzer.calculate_coverage_delta(sample_coverage_snapshot.id)

        assert delta is None

    def test_calculate_delta_coverage_regression(
        self,
        db_session,
        sample_workspace
    ):
        """Test delta calculation with coverage regression."""
        analyzer = TestCoverageAnalyzer(db_session)

        # Previous snapshot (higher coverage)
        previous = CoverageSnapshot(
            workspace_id=sample_workspace.id,
            lines_covered=900,
            lines_total=1000,
            coverage_percent=90.0,
            file_coverage={"app/foo.py": {"lines": 95.0}},
            commit_sha="prev123",
            branch_name="main",
            report_format="pytest",
            report_path="/tmp/repo",
        )
        db_session.add(previous)
        db_session.commit()

        # Current snapshot (lower coverage)
        current = CoverageSnapshot(
            workspace_id=sample_workspace.id,
            lines_covered=750,
            lines_total=1000,
            coverage_percent=75.0,
            file_coverage={"app/foo.py": {"lines": 70.0}},
            commit_sha="curr123",
            branch_name="main",
            report_format="pytest",
            report_path="/tmp/repo",
        )
        db_session.add(current)
        db_session.commit()
        db_session.refresh(current)

        delta = analyzer.calculate_coverage_delta(current.id, previous.id)

        assert delta is not None
        assert delta.improved is False
        assert delta.delta_percent == -15.0
        assert len(delta.regressed_files) == 1


class TestIdentifyUncoveredCode:
    """Test identify_uncovered_code method."""

    def test_identify_uncovered_code_basic(
        self,
        db_session,
        sample_coverage_snapshot
    ):
        """Test basic uncovered code identification."""
        analyzer = TestCoverageAnalyzer(db_session)

        result = analyzer.identify_uncovered_code(sample_coverage_snapshot.id)

        assert result["snapshot_id"] == sample_coverage_snapshot.id
        assert result["coverage_percent"] == 90.0
        assert result["coverage_grade"] == "A"
        assert result["total_uncovered_lines"] == 19  # 4 + 15
        assert result["files_with_gaps"] == 2

        # Check priority files
        priority = result["priority_files"]
        assert len(priority) == 2

        # File with most uncovered lines should be first
        assert priority[0]["path"] == "app/services/user.py"
        assert priority[0]["uncovered_count"] == 15
        assert priority[0]["coverage"] == 85.0

    def test_identify_uncovered_code_with_limits(
        self,
        db_session,
        sample_coverage_snapshot
    ):
        """Test uncovered code identification with limits."""
        analyzer = TestCoverageAnalyzer(db_session)

        result = analyzer.identify_uncovered_code(
            sample_coverage_snapshot.id,
            max_files=1,
            max_lines_per_file=5
        )

        # Only 1 file should be returned
        assert len(result["priority_files"]) == 1

        # Only 5 lines should be returned
        assert len(result["priority_files"][0]["uncovered_lines"]) == 5

    def test_identify_uncovered_code_no_snapshot(self, db_session):
        """Test uncovered code identification with invalid snapshot."""
        analyzer = TestCoverageAnalyzer(db_session)

        result = analyzer.identify_uncovered_code(99999)

        assert result == {}

    def test_identify_uncovered_code_priority_scoring(
        self,
        db_session,
        sample_workspace
    ):
        """Test priority scoring (more uncovered + lower coverage = higher priority)."""
        analyzer = TestCoverageAnalyzer(db_session)

        snapshot = CoverageSnapshot(
            workspace_id=sample_workspace.id,
            lines_covered=700,
            lines_total=1000,
            coverage_percent=70.0,
            file_coverage={
                "app/high_priority.py": {"lines": 50.0},  # 50 uncovered, 50% coverage
                "app/low_priority.py": {"lines": 90.0},   # 10 uncovered, 90% coverage
            },
            uncovered_lines={
                "app/high_priority.py": list(range(1, 51)),  # 50 lines
                "app/low_priority.py": list(range(1, 11)),   # 10 lines
            },
            commit_sha="abc123",
            branch_name="main",
            report_format="pytest",
            report_path="/tmp/repo",
        )
        db_session.add(snapshot)
        db_session.commit()
        db_session.refresh(snapshot)

        result = analyzer.identify_uncovered_code(snapshot.id)

        # high_priority should come first (50 * (100 - 50) = 2500)
        # vs low_priority (10 * (100 - 90) = 100)
        assert result["priority_files"][0]["path"] == "app/high_priority.py"
        assert result["priority_files"][0]["priority_score"] == 2500


class TestCoverageTrend:
    """Test get_coverage_trend method."""

    def test_coverage_trend_improving(
        self,
        db_session,
        sample_coverage_snapshots_trend
    ):
        """Test trend analysis for improving coverage."""
        analyzer = TestCoverageAnalyzer(db_session)
        workspace_id = sample_coverage_snapshots_trend[0].workspace_id

        trend = analyzer.get_coverage_trend(workspace_id, days=30)

        assert trend is not None
        assert trend.trend_direction == "improving"
        assert len(trend.snapshots) == 5
        assert trend.total_change == 10.0  # 75% -> 85%
        assert trend.min_coverage == 75.0
        assert trend.max_coverage == 85.0

    def test_coverage_trend_declining(
        self,
        db_session,
        sample_workspace
    ):
        """Test trend analysis for declining coverage."""
        # Create declining snapshots
        for i in range(3):
            snapshot = CoverageSnapshot(
                workspace_id=sample_workspace.id,
                lines_covered=900 - (i * 50),
                lines_total=1000,
                coverage_percent=90.0 - (i * 5.0),
                commit_sha=f"commit{i}",
                branch_name="main",
                report_format="pytest",
                report_path="/tmp/repo",
            )
            db_session.add(snapshot)
        db_session.commit()

        analyzer = TestCoverageAnalyzer(db_session)
        trend = analyzer.get_coverage_trend(sample_workspace.id, days=30)

        assert trend is not None
        assert trend.trend_direction == "declining"
        assert trend.total_change == -10.0

    def test_coverage_trend_stable(
        self,
        db_session,
        sample_workspace
    ):
        """Test trend analysis for stable coverage."""
        # Create stable snapshots (minor fluctuations)
        for i in range(3):
            snapshot = CoverageSnapshot(
                workspace_id=sample_workspace.id,
                lines_covered=850,
                lines_total=1000,
                coverage_percent=85.0,
                commit_sha=f"commit{i}",
                branch_name="main",
                report_format="pytest",
                report_path="/tmp/repo",
            )
            db_session.add(snapshot)
        db_session.commit()

        analyzer = TestCoverageAnalyzer(db_session)
        trend = analyzer.get_coverage_trend(sample_workspace.id, days=30)

        assert trend is not None
        assert trend.trend_direction == "stable"
        assert trend.total_change == 0.0

    def test_coverage_trend_insufficient_data(
        self,
        db_session,
        sample_coverage_snapshot
    ):
        """Test trend analysis with insufficient data."""
        analyzer = TestCoverageAnalyzer(db_session)

        trend = analyzer.get_coverage_trend(
            sample_coverage_snapshot.workspace_id,
            days=30
        )

        assert trend is None

    def test_coverage_trend_branch_filter(
        self,
        db_session,
        sample_workspace
    ):
        """Test trend analysis with branch filtering."""
        # Create snapshots on different branches
        for i in range(3):
            snapshot = CoverageSnapshot(
                workspace_id=sample_workspace.id,
                lines_covered=800 + (i * 50),
                lines_total=1000,
                coverage_percent=80.0 + (i * 5.0),
                commit_sha=f"commit{i}",
                branch_name="feature-branch" if i < 2 else "main",
                report_format="pytest",
                report_path="/tmp/repo",
            )
            db_session.add(snapshot)
        db_session.commit()

        analyzer = TestCoverageAnalyzer(db_session)
        trend = analyzer.get_coverage_trend(
            sample_workspace.id,
            days=30,
            branch_name="feature-branch"
        )

        assert trend is not None
        assert len(trend.snapshots) == 2  # Only feature-branch snapshots


class TestCompareSnapshots:
    """Test compare_snapshots method."""

    def test_compare_snapshots_improved(
        self,
        db_session,
        sample_workspace
    ):
        """Test snapshot comparison with improved coverage."""
        analyzer = TestCoverageAnalyzer(db_session)

        snapshot1 = CoverageSnapshot(
            workspace_id=sample_workspace.id,
            lines_covered=800,
            lines_total=1000,
            coverage_percent=80.0,
            file_coverage={
                "app/foo.py": {"lines": 75.0},
                "app/bar.py": {"lines": 85.0},
            },
            commit_sha="commit1",
            branch_name="main",
            report_format="pytest",
            report_path="/tmp/repo",
        )
        db_session.add(snapshot1)

        snapshot2 = CoverageSnapshot(
            workspace_id=sample_workspace.id,
            lines_covered=900,
            lines_total=1000,
            coverage_percent=90.0,
            file_coverage={
                "app/foo.py": {"lines": 95.0},
                "app/bar.py": {"lines": 85.0},
            },
            commit_sha="commit2",
            branch_name="main",
            report_format="pytest",
            report_path="/tmp/repo",
        )
        db_session.add(snapshot2)
        db_session.commit()
        db_session.refresh(snapshot1)
        db_session.refresh(snapshot2)

        result = analyzer.compare_snapshots(snapshot1.id, snapshot2.id)

        assert result["overall_delta"] == 10.0
        assert result["lines_delta"] == 100
        assert result["status"] == "improved"
        assert result["total_files_changed"] == 1

        # Only foo.py changed
        assert len(result["file_changes"]) == 1
        assert result["file_changes"][0]["path"] == "app/foo.py"
        assert result["file_changes"][0]["status"] == "improved"

    def test_compare_snapshots_regressed(
        self,
        db_session,
        sample_workspace
    ):
        """Test snapshot comparison with regressed coverage."""
        analyzer = TestCoverageAnalyzer(db_session)

        snapshot1 = CoverageSnapshot(
            workspace_id=sample_workspace.id,
            lines_covered=900,
            lines_total=1000,
            coverage_percent=90.0,
            file_coverage={"app/foo.py": {"lines": 95.0}},
            commit_sha="commit1",
            branch_name="main",
            report_format="pytest",
            report_path="/tmp/repo",
        )
        db_session.add(snapshot1)

        snapshot2 = CoverageSnapshot(
            workspace_id=sample_workspace.id,
            lines_covered=750,
            lines_total=1000,
            coverage_percent=75.0,
            file_coverage={"app/foo.py": {"lines": 70.0}},
            commit_sha="commit2",
            branch_name="main",
            report_format="pytest",
            report_path="/tmp/repo",
        )
        db_session.add(snapshot2)
        db_session.commit()
        db_session.refresh(snapshot1)
        db_session.refresh(snapshot2)

        result = analyzer.compare_snapshots(snapshot1.id, snapshot2.id)

        assert result["overall_delta"] == -15.0
        assert result["status"] == "regressed"
        assert result["file_changes"][0]["status"] == "regressed"

    def test_compare_snapshots_invalid(self, db_session):
        """Test comparison with invalid snapshot IDs."""
        analyzer = TestCoverageAnalyzer(db_session)

        result = analyzer.compare_snapshots(99999, 99998)

        assert result == {}


class TestGetLatestSnapshot:
    """Test get_latest_snapshot method."""

    def test_get_latest_snapshot(
        self,
        db_session,
        sample_coverage_snapshots_trend
    ):
        """Test getting the most recent snapshot."""
        analyzer = TestCoverageAnalyzer(db_session)
        workspace_id = sample_coverage_snapshots_trend[0].workspace_id

        latest = analyzer.get_latest_snapshot(workspace_id)

        assert latest is not None
        assert latest.id == sample_coverage_snapshots_trend[-1].id

    def test_get_latest_snapshot_with_branch(
        self,
        db_session,
        sample_workspace
    ):
        """Test getting latest snapshot filtered by branch."""
        # Create snapshots on different branches
        main_snapshot = CoverageSnapshot(
            workspace_id=sample_workspace.id,
            lines_covered=800,
            lines_total=1000,
            coverage_percent=80.0,
            commit_sha="main123",
            branch_name="main",
            report_format="pytest",
            report_path="/tmp/repo",
        )
        db_session.add(main_snapshot)
        db_session.commit()

        feature_snapshot = CoverageSnapshot(
            workspace_id=sample_workspace.id,
            lines_covered=850,
            lines_total=1000,
            coverage_percent=85.0,
            commit_sha="feature123",
            branch_name="feature",
            report_format="pytest",
            report_path="/tmp/repo",
        )
        db_session.add(feature_snapshot)
        db_session.commit()
        db_session.refresh(feature_snapshot)

        analyzer = TestCoverageAnalyzer(db_session)
        latest = analyzer.get_latest_snapshot(
            sample_workspace.id,
            branch_name="feature"
        )

        assert latest is not None
        assert latest.branch_name == "feature"
        assert latest.id == feature_snapshot.id

    def test_get_latest_snapshot_none(self, db_session, sample_workspace):
        """Test getting latest snapshot when none exist."""
        analyzer = TestCoverageAnalyzer(db_session)

        latest = analyzer.get_latest_snapshot(sample_workspace.id)

        assert latest is None
