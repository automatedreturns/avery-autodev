"""Validation tools for testing, building, and linting code."""

import json
import subprocess
from pathlib import Path

from .base import AgentTool, ToolContext, ToolResult


class RunTestsTool(AgentTool):
    """Run project tests to validate changes."""

    @property
    def name(self) -> str:
        return "run_tests"

    @property
    def description(self) -> str:
        return """Execute project tests to validate that changes work correctly.
Automatically detects test framework (pytest, jest, mocha, etc.) and runs tests.
Returns test results with passed/failed counts and error details."""

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "test_path": {
                    "type": "string",
                    "description": "Specific test file or directory to run (optional, runs all tests if empty)"
                },
                "test_pattern": {
                    "type": "string",
                    "description": "Pattern to match specific test names (optional)"
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (default: 300)"
                }
            },
            "required": []
        }

    def execute(self, params: dict, context: ToolContext) -> ToolResult:
        """Execute tests."""
        test_path = params.get("test_path", "")
        test_pattern = params.get("test_pattern")
        timeout = params.get("timeout", 300)

        try:
            # Detect test framework and run tests
            result = self._run_tests(
                context.repo_path,
                test_path,
                test_pattern,
                timeout
            )

            return result

        except Exception as e:
            return ToolResult(
                success=False,
                data={},
                error=f"Test execution failed: {str(e)}"
            )

    def _run_tests(
        self,
        repo_path: str,
        test_path: str,
        test_pattern: str | None,
        timeout: int
    ) -> ToolResult:
        """Run tests using detected framework."""
        repo = Path(repo_path)

        # Detect test framework
        framework = self._detect_framework(repo)

        if framework == "pytest":
            return self._run_pytest(repo_path, test_path, test_pattern, timeout)
        elif framework == "jest":
            return self._run_jest(repo_path, test_path, test_pattern, timeout)
        elif framework == "mocha":
            return self._run_mocha(repo_path, test_path, test_pattern, timeout)
        elif framework == "unittest":
            return self._run_unittest(repo_path, test_path, timeout)
        else:
            return ToolResult(
                success=False,
                data={},
                error="No test framework detected. Ensure pytest, jest, mocha, or unittest is configured.",
                suggestions=[
                    "Add test dependencies to requirements.txt or package.json",
                    "Create a test configuration file (pytest.ini, jest.config.js, etc.)",
                    "Ensure tests are in standard locations (tests/, __tests__, etc.)"
                ]
            )

    def _detect_framework(self, repo: Path) -> str | None:
        """Detect which test framework is being used."""
        # Check for Python frameworks
        if (repo / "pytest.ini").exists() or (repo / "pyproject.toml").exists():
            return "pytest"

        # Check for JavaScript frameworks
        if (repo / "jest.config.js").exists() or (repo / "jest.config.ts").exists():
            return "jest"

        package_json = repo / "package.json"
        if package_json.exists():
            try:
                with open(package_json) as f:
                    data = json.load(f)
                    scripts = data.get("scripts", {})
                    if "jest" in scripts.get("test", ""):
                        return "jest"
                    if "mocha" in scripts.get("test", ""):
                        return "mocha"
            except Exception:
                pass

        # Check for unittest (Python standard)
        if list(repo.glob("test*.py")) or list(repo.glob("**/test_*.py")):
            return "unittest"

        return None

    def _run_pytest(
        self,
        repo_path: str,
        test_path: str,
        test_pattern: str | None,
        timeout: int
    ) -> ToolResult:
        """Run pytest."""
        cmd = ["python", "-m", "pytest", "--tb=short", "-v", "--json-report", "--json-report-file=/tmp/pytest_report.json"]

        if test_path:
            cmd.append(test_path)

        if test_pattern:
            cmd.extend(["-k", test_pattern])

        try:
            result = subprocess.run(
                cmd,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            # Parse output
            return self._parse_pytest_output(result.stdout, result.stderr, result.returncode)

        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                data={},
                error=f"Tests timed out after {timeout} seconds",
                suggestions=["Increase timeout", "Check for hanging tests", "Run specific test subset"]
            )

    def _run_jest(
        self,
        repo_path: str,
        test_path: str,
        test_pattern: str | None,
        timeout: int
    ) -> ToolResult:
        """Run jest."""
        cmd = ["npm", "test", "--", "--json", "--verbose"]

        if test_path:
            cmd.append(test_path)

        if test_pattern:
            cmd.extend(["-t", test_pattern])

        try:
            result = subprocess.run(
                cmd,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            return self._parse_jest_output(result.stdout, result.stderr, result.returncode)

        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                data={},
                error=f"Tests timed out after {timeout} seconds"
            )

    def _run_mocha(
        self,
        repo_path: str,
        test_path: str,
        test_pattern: str | None,
        timeout: int
    ) -> ToolResult:
        """Run mocha."""
        cmd = ["npm", "test"]

        if test_path:
            cmd.append(test_path)

        try:
            result = subprocess.run(
                cmd,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            return self._parse_mocha_output(result.stdout, result.stderr, result.returncode)

        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                data={},
                error=f"Tests timed out after {timeout} seconds"
            )

    def _run_unittest(
        self,
        repo_path: str,
        test_path: str,
        timeout: int
    ) -> ToolResult:
        """Run Python unittest."""
        cmd = ["python", "-m", "unittest", "discover", "-v"]

        if test_path:
            cmd.extend(["-s", test_path])

        try:
            result = subprocess.run(
                cmd,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            return self._parse_unittest_output(result.stdout, result.stderr, result.returncode)

        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                data={},
                error=f"Tests timed out after {timeout} seconds"
            )

    def _parse_pytest_output(self, stdout: str, stderr: str, returncode: int) -> ToolResult:
        """Parse pytest output."""
        # Try to parse JSON report if available
        try:
            with open("/tmp/pytest_report.json") as f:
                report = json.load(f)
                summary = report.get("summary", {})

                return ToolResult(
                    success=returncode == 0,
                    data={
                        "status": "passed" if returncode == 0 else "failed",
                        "passed": summary.get("passed", 0),
                        "failed": summary.get("failed", 0),
                        "skipped": summary.get("skipped", 0),
                        "total": summary.get("total", 0),
                        "duration": summary.get("duration", 0),
                        "output": stdout[-2000:] if len(stdout) > 2000 else stdout
                    }
                )
        except Exception:
            pass

        # Fallback: parse text output
        lines = stdout.split('\n')
        summary_line = [l for l in lines if 'passed' in l.lower() or 'failed' in l.lower()]

        return ToolResult(
            success=returncode == 0,
            data={
                "status": "passed" if returncode == 0 else "failed",
                "output": stdout[-2000:] if len(stdout) > 2000 else stdout,
                "summary": summary_line[-1] if summary_line else "Test execution completed"
            }
        )

    def _parse_jest_output(self, stdout: str, stderr: str, returncode: int) -> ToolResult:
        """Parse jest output."""
        try:
            # Jest outputs JSON to stdout
            data = json.loads(stdout)

            return ToolResult(
                success=data.get("success", False),
                data={
                    "status": "passed" if data.get("success") else "failed",
                    "passed": data.get("numPassedTests", 0),
                    "failed": data.get("numFailedTests", 0),
                    "total": data.get("numTotalTests", 0),
                    "output": stderr[-2000:] if len(stderr) > 2000 else stderr
                }
            )
        except Exception:
            return ToolResult(
                success=returncode == 0,
                data={
                    "status": "passed" if returncode == 0 else "failed",
                    "output": (stdout + stderr)[-2000:]
                }
            )

    def _parse_mocha_output(self, stdout: str, stderr: str, returncode: int) -> ToolResult:
        """Parse mocha output."""
        return ToolResult(
            success=returncode == 0,
            data={
                "status": "passed" if returncode == 0 else "failed",
                "output": stdout[-2000:] if len(stdout) > 2000 else stdout
            }
        )

    def _parse_unittest_output(self, stdout: str, stderr: str, returncode: int) -> ToolResult:
        """Parse unittest output."""
        return ToolResult(
            success=returncode == 0,
            data={
                "status": "passed" if returncode == 0 else "failed",
                "output": (stdout + stderr)[-2000:]
            }
        )


class RunBuildTool(AgentTool):
    """Build the project to verify compilation."""

    @property
    def name(self) -> str:
        return "run_build"

    @property
    def description(self) -> str:
        return """Build the project to verify that code compiles without errors.
Automatically detects build system (npm, webpack, tsc, setuptools, etc.).
Returns build status and any compilation errors."""

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "Build target (e.g., 'production', 'development', default depends on project)"
                },
                "clean": {
                    "type": "boolean",
                    "description": "Clean build artifacts before building (default: false)"
                }
            },
            "required": []
        }

    def execute(self, params: dict, context: ToolContext) -> ToolResult:
        """Execute build."""
        target = params.get("target")
        clean = params.get("clean", False)

        try:
            repo = Path(context.repo_path)

            # Detect build system
            build_system = self._detect_build_system(repo)

            if not build_system:
                return ToolResult(
                    success=True,
                    data={
                        "status": "skipped",
                        "message": "No build system detected. Project may not require building."
                    }
                )

            # Run build
            if build_system == "npm":
                return self._run_npm_build(context.repo_path, target, clean)
            elif build_system == "typescript":
                return self._run_tsc_build(context.repo_path, clean)
            elif build_system == "python":
                return self._run_python_build(context.repo_path)
            else:
                return ToolResult(
                    success=False,
                    data={},
                    error=f"Unsupported build system: {build_system}"
                )

        except Exception as e:
            return ToolResult(
                success=False,
                data={},
                error=f"Build failed: {str(e)}"
            )

    def _detect_build_system(self, repo: Path) -> str | None:
        """Detect which build system is being used."""
        # Check for JavaScript/TypeScript build
        package_json = repo / "package.json"
        if package_json.exists():
            try:
                with open(package_json) as f:
                    data = json.load(f)
                    scripts = data.get("scripts", {})
                    if "build" in scripts:
                        return "npm"
            except Exception:
                pass

        # Check for TypeScript
        if (repo / "tsconfig.json").exists():
            return "typescript"

        # Check for Python build
        if (repo / "setup.py").exists() or (repo / "pyproject.toml").exists():
            return "python"

        return None

    def _run_npm_build(self, repo_path: str, target: str | None, clean: bool) -> ToolResult:
        """Run npm build."""
        try:
            if clean:
                subprocess.run(
                    ["npm", "run", "clean"],
                    cwd=repo_path,
                    capture_output=True,
                    timeout=60
                )

            cmd = ["npm", "run", "build"]
            if target:
                cmd.append(f"--{target}")

            result = subprocess.run(
                cmd,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=300
            )

            return ToolResult(
                success=result.returncode == 0,
                data={
                    "status": "success" if result.returncode == 0 else "failed",
                    "output": (result.stdout + result.stderr)[-2000:]
                }
            )

        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                data={},
                error="Build timed out after 300 seconds"
            )

    def _run_tsc_build(self, repo_path: str, clean: bool) -> ToolResult:
        """Run TypeScript compiler."""
        try:
            if clean:
                subprocess.run(
                    ["npx", "tsc", "--build", "--clean"],
                    cwd=repo_path,
                    capture_output=True,
                    timeout=60
                )

            result = subprocess.run(
                ["npx", "tsc", "--noEmit"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=180
            )

            return ToolResult(
                success=result.returncode == 0,
                data={
                    "status": "success" if result.returncode == 0 else "failed",
                    "output": (result.stdout + result.stderr)[-2000:]
                }
            )

        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                data={},
                error="TypeScript compilation timed out"
            )

    def _run_python_build(self, repo_path: str) -> ToolResult:
        """Run Python build."""
        try:
            # Just verify Python syntax for all files
            result = subprocess.run(
                ["python", "-m", "py_compile"] + list(Path(repo_path).glob("**/*.py")),
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=120
            )

            return ToolResult(
                success=result.returncode == 0,
                data={
                    "status": "success" if result.returncode == 0 else "failed",
                    "output": result.stderr if result.stderr else "All Python files compiled successfully"
                }
            )

        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                data={},
                error="Python compilation check timed out"
            )


class RunLinterTool(AgentTool):
    """Run code linter to check code quality."""

    @property
    def name(self) -> str:
        return "run_linter"

    @property
    def description(self) -> str:
        return """Run code linter/formatter to check code quality and style compliance.
Automatically detects linter (eslint, flake8, pylint, black, prettier).
Returns linting results with any issues found."""

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific files to lint (optional, lints all changed files if empty)"
                },
                "fix": {
                    "type": "boolean",
                    "description": "Auto-fix issues if possible (default: false)"
                }
            },
            "required": []
        }

    def execute(self, params: dict, context: ToolContext) -> ToolResult:
        """Execute linter."""
        files = params.get("files", [])
        fix = params.get("fix", False)

        try:
            repo = Path(context.repo_path)

            # Detect linter
            linters = self._detect_linters(repo)

            if not linters:
                return ToolResult(
                    success=True,
                    data={
                        "status": "skipped",
                        "message": "No linter configuration found"
                    }
                )

            # Run linters
            results = []
            for linter in linters:
                if linter == "eslint":
                    result = self._run_eslint(context.repo_path, files, fix)
                elif linter == "flake8":
                    result = self._run_flake8(context.repo_path, files)
                elif linter == "black":
                    result = self._run_black(context.repo_path, files, fix)
                elif linter == "prettier":
                    result = self._run_prettier(context.repo_path, files, fix)
                else:
                    continue

                results.append(result)

            # Combine results
            all_success = all(r.success for r in results)

            return ToolResult(
                success=all_success,
                data={
                    "status": "passed" if all_success else "issues_found",
                    "results": [r.data for r in results]
                }
            )

        except Exception as e:
            return ToolResult(
                success=False,
                data={},
                error=f"Linter execution failed: {str(e)}"
            )

    def _detect_linters(self, repo: Path) -> list[str]:
        """Detect which linters are configured."""
        linters = []

        # JavaScript/TypeScript linters
        if (repo / ".eslintrc.js").exists() or (repo / ".eslintrc.json").exists():
            linters.append("eslint")

        if (repo / ".prettierrc").exists() or (repo / "prettier.config.js").exists():
            linters.append("prettier")

        # Python linters
        if (repo / ".flake8").exists() or (repo / "setup.cfg").exists():
            linters.append("flake8")

        if (repo / "pyproject.toml").exists():
            linters.append("black")

        return linters

    def _run_eslint(self, repo_path: str, files: list[str], fix: bool) -> ToolResult:
        """Run ESLint."""
        cmd = ["npx", "eslint"]

        if fix:
            cmd.append("--fix")

        if files:
            cmd.extend(files)
        else:
            cmd.append(".")

        try:
            result = subprocess.run(
                cmd,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=120
            )

            return ToolResult(
                success=result.returncode == 0,
                data={
                    "linter": "eslint",
                    "status": "passed" if result.returncode == 0 else "issues_found",
                    "output": result.stdout[-1000:]
                }
            )

        except Exception as e:
            return ToolResult(
                success=False,
                data={"linter": "eslint"},
                error=str(e)
            )

    def _run_flake8(self, repo_path: str, files: list[str]) -> ToolResult:
        """Run flake8."""
        cmd = ["python", "-m", "flake8"]

        if files:
            cmd.extend(files)
        else:
            cmd.append(".")

        try:
            result = subprocess.run(
                cmd,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=120
            )

            return ToolResult(
                success=result.returncode == 0,
                data={
                    "linter": "flake8",
                    "status": "passed" if result.returncode == 0 else "issues_found",
                    "output": result.stdout[-1000:]
                }
            )

        except Exception as e:
            return ToolResult(
                success=False,
                data={"linter": "flake8"},
                error=str(e)
            )

    def _run_black(self, repo_path: str, files: list[str], fix: bool) -> ToolResult:
        """Run black formatter."""
        cmd = ["python", "-m", "black"]

        if not fix:
            cmd.append("--check")

        if files:
            cmd.extend(files)
        else:
            cmd.append(".")

        try:
            result = subprocess.run(
                cmd,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=120
            )

            return ToolResult(
                success=result.returncode == 0,
                data={
                    "linter": "black",
                    "status": "passed" if result.returncode == 0 else "issues_found",
                    "output": result.stdout[-1000:]
                }
            )

        except Exception as e:
            return ToolResult(
                success=False,
                data={"linter": "black"},
                error=str(e)
            )

    def _run_prettier(self, repo_path: str, files: list[str], fix: bool) -> ToolResult:
        """Run prettier formatter."""
        cmd = ["npx", "prettier"]

        if fix:
            cmd.append("--write")
        else:
            cmd.append("--check")

        if files:
            cmd.extend(files)
        else:
            cmd.append(".")

        try:
            result = subprocess.run(
                cmd,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=120
            )

            return ToolResult(
                success=result.returncode == 0,
                data={
                    "linter": "prettier",
                    "status": "passed" if result.returncode == 0 else "issues_found",
                    "output": result.stdout[-1000:]
                }
            )

        except Exception as e:
            return ToolResult(
                success=False,
                data={"linter": "prettier"},
                error=str(e)
            )


class TypeCheckTool(AgentTool):
    """Run type checker to verify type safety."""

    @property
    def name(self) -> str:
        return "type_check"

    @property
    def description(self) -> str:
        return """Run type checker to verify type safety in TypeScript or Python code.
Automatically detects type checker (tsc, mypy, pyright).
Returns type checking results with any type errors found."""

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific files to check (optional, checks all if empty)"
                }
            },
            "required": []
        }

    def execute(self, params: dict, context: ToolContext) -> ToolResult:
        """Execute type checker."""
        files = params.get("files", [])

        try:
            repo = Path(context.repo_path)

            # Detect type checker
            checker = self._detect_type_checker(repo)

            if not checker:
                return ToolResult(
                    success=True,
                    data={
                        "status": "skipped",
                        "message": "No type checker configuration found"
                    }
                )

            # Run type checker
            if checker == "typescript":
                return self._run_tsc(context.repo_path)
            elif checker == "mypy":
                return self._run_mypy(context.repo_path, files)
            elif checker == "pyright":
                return self._run_pyright(context.repo_path, files)

        except Exception as e:
            return ToolResult(
                success=False,
                data={},
                error=f"Type checking failed: {str(e)}"
            )

    def _detect_type_checker(self, repo: Path) -> str | None:
        """Detect which type checker is configured."""
        if (repo / "tsconfig.json").exists():
            return "typescript"

        if (repo / "mypy.ini").exists() or (repo / "pyproject.toml").exists():
            # Check if mypy is configured in pyproject.toml
            return "mypy"

        if (repo / "pyrightconfig.json").exists():
            return "pyright"

        return None

    def _run_tsc(self, repo_path: str) -> ToolResult:
        """Run TypeScript compiler for type checking."""
        try:
            result = subprocess.run(
                ["npx", "tsc", "--noEmit"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=180
            )

            return ToolResult(
                success=result.returncode == 0,
                data={
                    "checker": "typescript",
                    "status": "passed" if result.returncode == 0 else "errors_found",
                    "output": result.stdout[-2000:]
                }
            )

        except Exception as e:
            return ToolResult(
                success=False,
                data={"checker": "typescript"},
                error=str(e)
            )

    def _run_mypy(self, repo_path: str, files: list[str]) -> ToolResult:
        """Run mypy type checker."""
        cmd = ["python", "-m", "mypy"]

        if files:
            cmd.extend(files)
        else:
            cmd.append(".")

        try:
            result = subprocess.run(
                cmd,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=180
            )

            return ToolResult(
                success=result.returncode == 0,
                data={
                    "checker": "mypy",
                    "status": "passed" if result.returncode == 0 else "errors_found",
                    "output": result.stdout[-2000:]
                }
            )

        except Exception as e:
            return ToolResult(
                success=False,
                data={"checker": "mypy"},
                error=str(e)
            )

    def _run_pyright(self, repo_path: str, files: list[str]) -> ToolResult:
        """Run pyright type checker."""
        cmd = ["pyright"]

        if files:
            cmd.extend(files)

        try:
            result = subprocess.run(
                cmd,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=180
            )

            return ToolResult(
                success=result.returncode == 0,
                data={
                    "checker": "pyright",
                    "status": "passed" if result.returncode == 0 else "errors_found",
                    "output": result.stdout[-2000:]
                }
            )

        except Exception as e:
            return ToolResult(
                success=False,
                data={"checker": "pyright"},
                error=str(e)
            )
