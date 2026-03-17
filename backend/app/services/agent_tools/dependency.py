"""Dependency management tools."""

import json
import subprocess
from pathlib import Path

from .base import AgentTool, ToolContext, ToolResult


class InstallDependenciesTool(AgentTool):
    """Install or update project dependencies."""

    @property
    def name(self) -> str:
        return "install_dependencies"

    @property
    def description(self) -> str:
        return """Install or update project dependencies.
Automatically detects package manager (npm, pip, etc.) and installs packages.
Use this when you need to add new libraries or update existing ones.
Note: This operation requires user approval and will modify package files."""

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "packages": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Package names with optional versions (e.g., ['requests>=2.28.0', 'lodash@4.17.21'])"
                },
                "dev": {
                    "type": "boolean",
                    "description": "Install as dev/development dependency (default: false)"
                }
            },
            "required": ["packages"]
        }

    def execute(self, params: dict, context: ToolContext) -> ToolResult:
        """Execute dependency installation."""
        packages = params["packages"]
        dev = params.get("dev", False)

        if not packages:
            return ToolResult(
                success=False,
                data={},
                error="No packages specified"
            )

        try:
            repo = Path(context.repo_path)

            # Detect package manager
            pkg_manager = self._detect_package_manager(repo)

            if not pkg_manager:
                return ToolResult(
                    success=False,
                    data={},
                    error="No package manager detected. Ensure package.json or requirements.txt exists.",
                    suggestions=[
                        "Create package.json for npm projects",
                        "Create requirements.txt for Python projects"
                    ]
                )

            # Install packages
            if pkg_manager == "npm":
                return self._install_npm(context.repo_path, packages, dev)
            elif pkg_manager == "pip":
                return self._install_pip(context.repo_path, packages, dev)
            else:
                return ToolResult(
                    success=False,
                    data={},
                    error=f"Unsupported package manager: {pkg_manager}"
                )

        except Exception as e:
            return ToolResult(
                success=False,
                data={},
                error=f"Dependency installation failed: {str(e)}"
            )

    def _detect_package_manager(self, repo: Path) -> str | None:
        """Detect which package manager is being used."""
        if (repo / "package.json").exists():
            return "npm"
        elif (repo / "requirements.txt").exists() or (repo / "setup.py").exists():
            return "pip"
        return None

    def _install_npm(self, repo_path: str, packages: list[str], dev: bool) -> ToolResult:
        """Install npm packages."""
        try:
            cmd = ["npm", "install"]

            if dev:
                cmd.append("--save-dev")

            cmd.extend(packages)

            result = subprocess.run(
                cmd,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode != 0:
                return ToolResult(
                    success=False,
                    data={},
                    error=f"npm install failed: {result.stderr}",
                    suggestions=[
                        "Check package names are correct",
                        "Verify npm registry is accessible",
                        "Check for version conflicts"
                    ]
                )

            return ToolResult(
                success=True,
                data={
                    "installed": packages,
                    "package_manager": "npm",
                    "dev": dev,
                    "message": f"Successfully installed {len(packages)} package(s)"
                }
            )

        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                data={},
                error="Installation timed out after 300 seconds"
            )

    def _install_pip(self, repo_path: str, packages: list[str], dev: bool) -> ToolResult:
        """Install pip packages."""
        try:
            cmd = ["python", "-m", "pip", "install"]

            cmd.extend(packages)

            result = subprocess.run(
                cmd,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode != 0:
                return ToolResult(
                    success=False,
                    data={},
                    error=f"pip install failed: {result.stderr}",
                    suggestions=[
                        "Check package names are correct",
                        "Verify PyPI is accessible",
                        "Check for version conflicts"
                    ]
                )

            # Update requirements.txt if it exists
            requirements_file = Path(repo_path) / "requirements.txt"
            if requirements_file.exists():
                with open(requirements_file, 'a') as f:
                    for package in packages:
                        f.write(f"\n{package}")

            return ToolResult(
                success=True,
                data={
                    "installed": packages,
                    "package_manager": "pip",
                    "message": f"Successfully installed {len(packages)} package(s)",
                    "note": "Added to requirements.txt" if requirements_file.exists() else None
                }
            )

        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                data={},
                error="Installation timed out after 300 seconds"
            )


class CheckDependenciesTool(AgentTool):
    """Check project dependencies for issues."""

    @property
    def name(self) -> str:
        return "check_dependencies"

    @property
    def description(self) -> str:
        return """Check project dependencies for issues like outdated versions or vulnerabilities.
Provides information about installed packages and their status."""

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "check_outdated": {
                    "type": "boolean",
                    "description": "Check for outdated packages (default: false)"
                },
                "check_security": {
                    "type": "boolean",
                    "description": "Check for security vulnerabilities (default: false)"
                }
            },
            "required": []
        }

    def execute(self, params: dict, context: ToolContext) -> ToolResult:
        """Execute dependency check."""
        check_outdated = params.get("check_outdated", False)
        check_security = params.get("check_security", False)

        try:
            repo = Path(context.repo_path)

            # Detect package manager
            pkg_manager = self._detect_package_manager(repo)

            if not pkg_manager:
                return ToolResult(
                    success=True,
                    data={
                        "status": "no_dependencies",
                        "message": "No dependency files found"
                    }
                )

            # Check dependencies
            if pkg_manager == "npm":
                return self._check_npm(context.repo_path, check_outdated, check_security)
            elif pkg_manager == "pip":
                return self._check_pip(context.repo_path, check_outdated)
            else:
                return ToolResult(
                    success=False,
                    data={},
                    error=f"Unsupported package manager: {pkg_manager}"
                )

        except Exception as e:
            return ToolResult(
                success=False,
                data={},
                error=f"Dependency check failed: {str(e)}"
            )

    def _detect_package_manager(self, repo: Path) -> str | None:
        """Detect which package manager is being used."""
        if (repo / "package.json").exists():
            return "npm"
        elif (repo / "requirements.txt").exists():
            return "pip"
        return None

    def _check_npm(self, repo_path: str, check_outdated: bool, check_security: bool) -> ToolResult:
        """Check npm dependencies."""
        issues = []

        # Check for outdated packages
        if check_outdated:
            try:
                result = subprocess.run(
                    ["npm", "outdated", "--json"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=60
                )

                if result.stdout:
                    outdated = json.loads(result.stdout)
                    if outdated:
                        issues.append({
                            "type": "outdated",
                            "count": len(outdated),
                            "packages": list(outdated.keys())[:10]
                        })
            except Exception:
                pass

        # Check for security vulnerabilities
        if check_security:
            try:
                result = subprocess.run(
                    ["npm", "audit", "--json"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=60
                )

                if result.stdout:
                    audit = json.loads(result.stdout)
                    vulnerabilities = audit.get("metadata", {}).get("vulnerabilities", {})

                    total_vulns = sum(vulnerabilities.values()) if vulnerabilities else 0

                    if total_vulns > 0:
                        issues.append({
                            "type": "security",
                            "count": total_vulns,
                            "severity": vulnerabilities
                        })
            except Exception:
                pass

        return ToolResult(
            success=True,
            data={
                "status": "issues_found" if issues else "healthy",
                "issues": issues,
                "package_manager": "npm"
            }
        )

    def _check_pip(self, repo_path: str, check_outdated: bool) -> ToolResult:
        """Check pip dependencies."""
        issues = []

        # Check for outdated packages
        if check_outdated:
            try:
                result = subprocess.run(
                    ["python", "-m", "pip", "list", "--outdated", "--format=json"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=60
                )

                if result.stdout:
                    outdated = json.loads(result.stdout)
                    if outdated:
                        issues.append({
                            "type": "outdated",
                            "count": len(outdated),
                            "packages": [pkg["name"] for pkg in outdated[:10]]
                        })
            except Exception:
                pass

        return ToolResult(
            success=True,
            data={
                "status": "issues_found" if issues else "healthy",
                "issues": issues,
                "package_manager": "pip"
            }
        )
