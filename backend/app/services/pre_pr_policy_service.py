"""
Pre-PR Policy Enforcement Service

This service handles coverage collection and test policy enforcement
before pull requests are created by the coding agent.
"""

import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

from sqlalchemy.orm import Session

from app.models.workspace import Workspace
from app.models.workspace_task import WorkspaceTask
from app.services.test_coverage_analyzer import TestCoverageAnalyzer
from app.services.test_policy_enforcer import TestPolicyEnforcer


class PrePRPolicyService:
    """Service for enforcing test policies before PR creation."""

    @staticmethod
    def collect_coverage(repo_path: str, workspace: Workspace) -> Optional[Dict[str, Any]]:
        """
        Run tests with coverage collection in the repository.

        Args:
            repo_path: Path to the local repository clone
            workspace: Workspace object for context

        Returns:
            Coverage data dict or None if collection failed:
            {
                "coverage_percent": 85.5,
                "lines_covered": 855,
                "lines_total": 1000,
                "file_coverage": {...},
                "uncovered_lines": {...},
                "uncovered_functions": [...]
            }
        """
        try:
            repo_path = Path(repo_path)
            if not repo_path.exists():
                logger.error(f"Repository path does not exist: {repo_path}")
                return None

            logger.info(f"Collecting coverage for {workspace.name} at {repo_path}")

            # Run tests with coverage
            # Try pytest first (most common), then fallback to other test runners
            coverage_data = PrePRPolicyService._run_pytest_coverage(repo_path)

            if not coverage_data:
                # Try other test runners if pytest fails
                coverage_data = PrePRPolicyService._run_npm_coverage(repo_path)

            if coverage_data:
                logger.info(f"Coverage collected: {coverage_data.get('coverage_percent', 0):.1f}%")

            return coverage_data

        except Exception as e:
            logger.error(f"Failed to collect coverage: {str(e)}")
            return None

    @staticmethod
    def _run_pytest_coverage(repo_path: Path) -> Optional[Dict[str, Any]]:
        """Run pytest with coverage and parse results."""
        try:
            # Check if pytest.ini or pyproject.toml exists (Python project)
            has_pytest = (
                (repo_path / "pytest.ini").exists() or
                (repo_path / "pyproject.toml").exists() or
                (repo_path / "setup.py").exists() or
                (repo_path / "requirements.txt").exists()
            )

            if not has_pytest:
                logger.debug("Not a Python project, skipping pytest coverage")
                return None

            logger.debug("Running pytest with coverage...")

            # Run pytest with coverage report as JSON
            result = subprocess.run(
                ["pytest", "--cov=.", "--cov-report=json", "--cov-report=term-missing", "-v"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            # Coverage JSON is saved to .coverage.json
            coverage_json_path = repo_path / ".coverage.json"
            if not coverage_json_path.exists():
                # Try coverage.json (alternative name)
                coverage_json_path = repo_path / "coverage.json"

            if not coverage_json_path.exists():
                logger.debug("No coverage JSON file found")
                return None

            # Parse coverage JSON
            with open(coverage_json_path, 'r') as f:
                coverage_json = json.load(f)

            # Transform to our format
            return PrePRPolicyService._transform_pytest_coverage(coverage_json, repo_path)

        except subprocess.TimeoutExpired:
            logger.error("Pytest coverage timeout (5 minutes)")
            return None
        except FileNotFoundError:
            logger.debug("pytest not found in PATH")
            return None
        except Exception as e:
            logger.error(f"Failed to run pytest coverage: {str(e)}")
            return None

    @staticmethod
    def _transform_pytest_coverage(coverage_json: Dict, repo_path: Path) -> Dict[str, Any]:
        """Transform pytest coverage JSON to our format."""
        try:
            totals = coverage_json.get("totals", {})
            files = coverage_json.get("files", {})

            # Calculate overall coverage
            covered_lines = totals.get("covered_lines", 0)
            num_statements = totals.get("num_statements", 0)
            coverage_percent = totals.get("percent_covered", 0.0)

            # Build file-level coverage
            file_coverage = {}
            uncovered_lines = {}
            uncovered_functions = []

            for file_path, file_data in files.items():
                # Make path relative to repo root
                rel_path = str(Path(file_path).relative_to(repo_path)) if repo_path else file_path

                file_coverage[rel_path] = {
                    "lines": file_data.get("summary", {}).get("percent_covered", 0.0),
                    "lines_covered": file_data.get("summary", {}).get("covered_lines", 0),
                    "lines_total": file_data.get("summary", {}).get("num_statements", 0),
                }

                # Get missing line numbers
                missing_lines = file_data.get("missing_lines", [])
                if missing_lines:
                    uncovered_lines[rel_path] = missing_lines

            return {
                "coverage_percent": coverage_percent,
                "lines_covered": covered_lines,
                "lines_total": num_statements,
                "file_coverage": file_coverage,
                "uncovered_lines": uncovered_lines,
                "uncovered_functions": uncovered_functions,
            }

        except Exception as e:
            logger.error(f"Failed to transform pytest coverage: {str(e)}")
            return {
                "coverage_percent": 0.0,
                "lines_covered": 0,
                "lines_total": 0,
                "file_coverage": {},
                "uncovered_lines": {},
                "uncovered_functions": [],
            }

    @staticmethod
    def _run_npm_coverage(repo_path: Path) -> Optional[Dict[str, Any]]:
        """Run npm test with coverage for JavaScript/TypeScript projects."""
        try:
            # Check if package.json exists (Node.js project)
            package_json = repo_path / "package.json"
            if not package_json.exists():
                logger.debug("Not a Node.js project, skipping npm coverage")
                return None

            logger.debug("Running npm test with coverage...")

            # Run npm test (many projects have "test" script configured with coverage)
            result = subprocess.run(
                ["npm", "test", "--", "--coverage", "--coverageReporters=json"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            # Coverage JSON is typically at coverage/coverage-summary.json
            coverage_json_path = repo_path / "coverage" / "coverage-summary.json"
            if not coverage_json_path.exists():
                logger.debug("No coverage summary JSON found")
                return None

            # Parse coverage JSON
            with open(coverage_json_path, 'r') as f:
                coverage_json = json.load(f)

            # Transform to our format
            return PrePRPolicyService._transform_npm_coverage(coverage_json, repo_path)

        except subprocess.TimeoutExpired:
            logger.error("npm test coverage timeout (5 minutes)")
            return None
        except FileNotFoundError:
            logger.debug("npm not found in PATH")
            return None
        except Exception as e:
            logger.error(f"Failed to run npm coverage: {str(e)}")
            return None

    @staticmethod
    def _transform_npm_coverage(coverage_json: Dict, repo_path: Path) -> Dict[str, Any]:
        """Transform npm coverage JSON to our format."""
        try:
            # Get total summary
            total = coverage_json.get("total", {})
            lines = total.get("lines", {})

            coverage_percent = lines.get("pct", 0.0)
            covered_lines = lines.get("covered", 0)
            total_lines = lines.get("total", 0)

            # Build file-level coverage
            file_coverage = {}
            uncovered_lines = {}

            for file_path, file_data in coverage_json.items():
                if file_path == "total":
                    continue

                # Make path relative
                rel_path = str(Path(file_path).relative_to(repo_path)) if repo_path else file_path

                file_lines = file_data.get("lines", {})
                file_coverage[rel_path] = {
                    "lines": file_lines.get("pct", 0.0),
                    "lines_covered": file_lines.get("covered", 0),
                    "lines_total": file_lines.get("total", 0),
                }

                # Note: npm coverage doesn't provide line-by-line info easily
                # Would need to parse coverage/lcov.info for that

            return {
                "coverage_percent": coverage_percent,
                "lines_covered": covered_lines,
                "lines_total": total_lines,
                "file_coverage": file_coverage,
                "uncovered_lines": uncovered_lines,
                "uncovered_functions": [],
            }

        except Exception as e:
            logger.error(f"Failed to transform npm coverage: {str(e)}")
            return {
                "coverage_percent": 0.0,
                "lines_covered": 0,
                "lines_total": 0,
                "file_coverage": {},
                "uncovered_lines": {},
                "uncovered_functions": [],
            }

    @staticmethod
    def enforce_policies_before_pr(
        db: Session,
        workspace: Workspace,
        task: WorkspaceTask,
        coverage_data: Dict[str, Any],
        commit_sha: str,
        branch_name: str
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[int]]:
        """
        Enforce test policies before allowing PR creation.

        Args:
            db: Database session
            workspace: Workspace object
            task: WorkspaceTask object
            coverage_data: Coverage data from collect_coverage()
            commit_sha: Git commit SHA
            branch_name: Git branch name

        Returns:
            Tuple of (should_create_pr: bool, policy_decision: dict, snapshot_id: int)
            - If should_create_pr is False, PR creation should be blocked
            - policy_decision contains violations, warnings, and fix suggestions
            - snapshot_id is the created coverage snapshot ID
        """
        try:
            logger.info(f"Enforcing test policies for task {task.id}")

            # Create coverage snapshot
            analyzer = TestCoverageAnalyzer(db)
            snapshot = analyzer.create_snapshot(
                workspace_id=workspace.id,
                coverage_data=coverage_data,
                commit_sha=commit_sha,
                branch_name=branch_name,
                pr_number=None  # No PR yet
            )

            logger.info(f"Created coverage snapshot {snapshot.id}")

            # Get test policy for workspace
            test_policy = db.query(workspace.__class__).filter_by(id=workspace.id).first()
            if not test_policy or not test_policy.test_policy_enabled:
                logger.info("Test policy not enabled for workspace, allowing PR creation")
                return True, None, snapshot.id

            # Enforce policies
            enforcer = TestPolicyEnforcer(db)
            policy_decision = enforcer.enforce_policies(
                workspace_id=workspace.id,
                current_snapshot_id=snapshot.id,
                change_type="feature"  # Assume feature for agent tasks
            )

            # Save policy decision to task
            task.pre_pr_policy_check = {
                "passed": policy_decision.passed,
                "violations": [v.dict() for v in policy_decision.violations],
                "warnings": [w.dict() for w in policy_decision.warnings],
                "summary": policy_decision.summary,
                "checked_at": datetime.utcnow().isoformat()
            }
            task.coverage_snapshot_id = snapshot.id
            db.commit()

            logger.info(f"Policy decision: passed={policy_decision.passed}, violations={len(policy_decision.violations)}")

            # Check if there are ERROR-level violations
            error_violations = [v for v in policy_decision.violations if v.severity == "error"]

            if error_violations:
                logger.warning(f"{len(error_violations)} error-level policy violations found, blocking PR creation")
                return False, policy_decision.dict(), snapshot.id

            if policy_decision.warnings:
                logger.info(f"{len(policy_decision.warnings)} warnings found, allowing PR with warning comment")

            return True, policy_decision.dict(), snapshot.id

        except Exception as e:
            logger.error(f"Failed to enforce policies: {str(e)}", exc_info=True)
            # On error, allow PR creation but log the issue
            return True, None, None

    @staticmethod
    def format_policy_violations_for_user(policy_decision: Dict[str, Any]) -> str:
        """
        Format policy violations into a user-friendly message.

        Args:
            policy_decision: Policy decision dict from enforce_policies_before_pr

        Returns:
            Formatted message string for display to user
        """
        if not policy_decision:
            return ""

        violations = policy_decision.get("violations", [])
        warnings = policy_decision.get("warnings", [])

        if not violations and not warnings:
            return "✅ All test policies passed!"

        message_parts = []

        # Format error violations
        if violations:
            error_violations = [v for v in violations if v.get("severity") == "error"]
            if error_violations:
                message_parts.append("## ❌ Policy Violations (Blocking PR Creation)\n")
                for v in error_violations:
                    message_parts.append(f"**{v.get('rule', 'Unknown')}**")
                    message_parts.append(f"- {v.get('message', 'No message')}")
                    if v.get("fix_suggestion"):
                        message_parts.append(f"- **Fix**: {v['fix_suggestion']}")
                    if v.get("affected_files"):
                        message_parts.append(f"- **Files**: {', '.join(v['affected_files'][:5])}")
                    message_parts.append("")

        # Format warnings
        if warnings:
            message_parts.append("## ⚠️ Policy Warnings\n")
            for w in warnings:
                message_parts.append(f"**{w.get('rule', 'Unknown')}**")
                message_parts.append(f"- {w.get('message', 'No message')}")
                message_parts.append("")

        return "\n".join(message_parts)

    @staticmethod
    def format_policy_comment_for_pr(policy_decision: Dict[str, Any], coverage_percent: float) -> str:
        """
        Format policy decision as a GitHub PR comment.

        Args:
            policy_decision: Policy decision dict
            coverage_percent: Coverage percentage

        Returns:
            Formatted PR comment body
        """
        warnings = policy_decision.get("warnings", [])

        if not warnings:
            return f"""## ✅ Test Policy Check Passed

**Coverage**: {coverage_percent:.1f}%

All test policy requirements have been met for this PR.
"""

        comment = f"""## ⚠️ Test Policy Check - Warnings

**Coverage**: {coverage_percent:.1f}%

This PR passes the minimum requirements but has the following warnings:

"""
        for w in warnings:
            comment += f"- **{w.get('rule', 'Unknown')}**: {w.get('message', 'No message')}\n"

        comment += "\nThese warnings don't block the PR but should be addressed when possible.\n"

        return comment
