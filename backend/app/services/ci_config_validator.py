"""CI Configuration Validator - Identifies missing or misconfigured CI checks."""

import logging
import yaml
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class CIConfigValidator:
    """Validate GitHub Actions workflow configuration and suggest improvements."""

    RECOMMENDED_CHECKS = {
        "backend": [
            {"name": "tests", "description": "Run pytest tests with coverage", "critical": True},
            {"name": "lint", "description": "Run ruff linter", "critical": True},
            {"name": "typecheck", "description": "Run mypy type checking", "critical": False},
            {"name": "security", "description": "Run security scanning (bandit)", "critical": False},
        ],
        "frontend": [
            {"name": "tests", "description": "Run Jest/Vitest tests", "critical": False},
            {"name": "lint", "description": "Run ESLint", "critical": True},
            {"name": "typecheck", "description": "Run TypeScript compiler", "critical": True},
            {"name": "build", "description": "Build production bundle", "critical": True},
        ]
    }

    def __init__(self, repo_path: str):
        """
        Initialize validator with repository path.

        Args:
            repo_path: Path to local repository clone
        """
        self.repo_path = Path(repo_path)

    def validate_workflow_exists(self) -> tuple[bool, str]:
        """
        Check if GitHub Actions workflow file exists.

        Returns:
            Tuple of (exists: bool, path: str)
        """
        workflow_paths = [
            ".github/workflows/agent-pr-validation.yml",
            ".github/workflows/agent-pr-validation.yaml",
            ".github/workflows/ci.yml",
            ".github/workflows/ci.yaml",
        ]

        for path in workflow_paths:
            full_path = self.repo_path / path
            if full_path.exists():
                return True, str(full_path)

        return False, ""

    def parse_workflow(self, workflow_path: str) -> Optional[dict]:
        """
        Parse GitHub Actions workflow YAML.

        Args:
            workflow_path: Path to workflow file

        Returns:
            Parsed workflow dict or None if parsing fails
        """
        try:
            with open(workflow_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to parse workflow file: {e}")
            return None

    def identify_missing_checks(self, workflow: dict) -> dict:
        """
        Identify missing recommended checks in workflow.

        Args:
            workflow: Parsed workflow dict

        Returns:
            Dictionary with missing checks for backend and frontend
        """
        missing = {
            "backend": [],
            "frontend": [],
            "critical_missing": []
        }

        if not workflow or "jobs" not in workflow:
            # No jobs at all - all checks missing
            missing["backend"] = self.RECOMMENDED_CHECKS["backend"]
            missing["frontend"] = self.RECOMMENDED_CHECKS["frontend"]
            missing["critical_missing"] = [
                check for check in self.RECOMMENDED_CHECKS["backend"] + self.RECOMMENDED_CHECKS["frontend"]
                if check["critical"]
            ]
            return missing

        # Check each job
        for job_name, job_config in workflow["jobs"].items():
            if "backend" in job_name.lower() or "python" in job_name.lower():
                self._check_backend_job(job_config, missing)
            elif "frontend" in job_name.lower() or "node" in job_name.lower():
                self._check_frontend_job(job_config, missing)

        return missing

    def _check_backend_job(self, job_config: dict, missing: dict):
        """Check backend job for missing checks."""
        steps = job_config.get("steps", [])
        step_names = [step.get("name", "").lower() for step in steps]
        step_runs = [step.get("run", "").lower() for step in steps]

        for check in self.RECOMMENDED_CHECKS["backend"]:
            check_name = check["name"]
            found = False

            # Check if step name or command contains check name
            for name in step_names:
                if check_name in name:
                    found = True
                    break

            if not found:
                for run in step_runs:
                    if check_name in run or (check_name == "tests" and "pytest" in run):
                        found = True
                        break

            if not found:
                missing["backend"].append(check)
                if check["critical"]:
                    missing["critical_missing"].append(check)

    def _check_frontend_job(self, job_config: dict, missing: dict):
        """Check frontend job for missing checks."""
        steps = job_config.get("steps", [])
        step_names = [step.get("name", "").lower() for step in steps]
        step_runs = [step.get("run", "").lower() for step in steps]

        for check in self.RECOMMENDED_CHECKS["frontend"]:
            check_name = check["name"]
            found = False

            for name in step_names:
                if check_name in name:
                    found = True
                    break

            if not found:
                for run in step_runs:
                    if check_name in run:
                        found = True
                        break

            if not found:
                missing["frontend"].append(check)
                if check["critical"]:
                    missing["critical_missing"].append(check)

    def generate_workflow_suggestions(self, missing: dict) -> str:
        """
        Generate human-readable suggestions for missing checks.

        Args:
            missing: Dict from identify_missing_checks()

        Returns:
            Formatted suggestion string
        """
        suggestions = []

        if missing["critical_missing"]:
            suggestions.append("⚠️  CRITICAL: Missing essential checks:")
            for check in missing["critical_missing"]:
                suggestions.append(f"  • {check['name']}: {check['description']}")

        if missing["backend"]:
            suggestions.append("\n📦 Backend checks to add:")
            for check in missing["backend"]:
                icon = "🔴" if check["critical"] else "🟡"
                suggestions.append(f"  {icon} {check['name']}: {check['description']}")

        if missing["frontend"]:
            suggestions.append("\n🎨 Frontend checks to add:")
            for check in missing["frontend"]:
                icon = "🔴" if check["critical"] else "🟡"
                suggestions.append(f"  {icon} {check['name']}: {check['description']}")

        if not suggestions:
            return "✅ All recommended checks are present!"

        return "\n".join(suggestions)

    def validate_webhook_configured(self, workflow: dict) -> tuple[bool, str]:
        """
        Check if workflow sends webhook to Avery backend.

        Args:
            workflow: Parsed workflow dict

        Returns:
            Tuple of (configured: bool, message: str)
        """
        if not workflow or "jobs" not in workflow:
            return False, "No jobs found in workflow"

        for job_name, job_config in workflow["jobs"].items():
            steps = job_config.get("steps", [])
            for step in steps:
                if "notify" in step.get("name", "").lower() or "avery" in step.get("name", "").lower():
                    run_command = step.get("run", "")
                    if "/api/v1/ci/webhook" in run_command:
                        return True, "Webhook configured correctly"

        return False, "Webhook notification not found. Add a step that POSTs to /api/v1/ci/webhook"

    def full_validation_report(self) -> dict:
        """
        Generate complete validation report for repository.

        Returns:
            Dictionary with validation results and suggestions
        """
        report = {
            "workflow_exists": False,
            "workflow_path": "",
            "missing_checks": {},
            "suggestions": "",
            "webhook_configured": False,
            "webhook_message": "",
            "overall_status": "fail"
        }

        # Check if workflow exists
        exists, path = self.validate_workflow_exists()
        report["workflow_exists"] = exists
        report["workflow_path"] = path

        if not exists:
            report["suggestions"] = "❌ No GitHub Actions workflow found. Create .github/workflows/agent-pr-validation.yml"
            return report

        # Parse workflow
        workflow = self.parse_workflow(path)
        if not workflow:
            report["suggestions"] = "❌ Failed to parse workflow file. Check YAML syntax."
            return report

        # Identify missing checks
        missing = self.identify_missing_checks(workflow)
        report["missing_checks"] = missing
        report["suggestions"] = self.generate_workflow_suggestions(missing)

        # Check webhook configuration
        webhook_ok, webhook_msg = self.validate_webhook_configured(workflow)
        report["webhook_configured"] = webhook_ok
        report["webhook_message"] = webhook_msg

        # Determine overall status
        if webhook_ok and not missing["critical_missing"]:
            report["overall_status"] = "good"
        elif webhook_ok or not missing["critical_missing"]:
            report["overall_status"] = "needs_improvement"
        else:
            report["overall_status"] = "fail"

        return report
