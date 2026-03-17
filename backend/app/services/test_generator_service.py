"""Test Generator Service - Automatically generates tests using Claude AI."""

import json
import logging
import re
from pathlib import Path
from typing import Optional

import anthropic

from app.core.config import settings
from app.engine.plugins import ExecutionContext, ExecutionUsage, get_plugin

logger = logging.getLogger(__name__)


class TestFile:
    """Represents a generated test file."""

    def __init__(
        self,
        test_file_path: str,
        test_content: str,
        tests_generated: list[dict],
        source_file: str
    ):
        self.test_file_path = test_file_path
        self.test_content = test_content
        self.tests_generated = tests_generated
        self.source_file = source_file

    def to_dict(self) -> dict:
        return {
            "test_file_path": self.test_file_path,
            "test_content": self.test_content,
            "tests_generated": self.tests_generated,
            "source_file": self.source_file
        }


class TestGeneratorService:
    """Generate comprehensive tests using Claude AI."""

    # Supported test frameworks
    TEST_FRAMEWORKS = {
        "python": ["pytest", "unittest"],
        "javascript": ["jest", "mocha", "vitest"],
        "typescript": ["jest", "vitest"],
    }

    def __init__(self):
        """Initialize test generator with Claude client."""
        plugin = get_plugin()
        api_key = plugin.resolve_api_key("anthropic") or settings.ANTHROPIC_API_KEY
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-5-20250929"
        self._plugin = plugin

    def detect_language(self, file_path: str) -> Optional[str]:
        """
        Detect programming language from file extension.

        Args:
            file_path: Path to source file

        Returns:
            Language identifier or None
        """
        ext_to_lang = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
        }
        ext = Path(file_path).suffix
        return ext_to_lang.get(ext)

    def detect_test_framework(
        self,
        language: str,
        workspace_path: str
    ) -> str:
        """
        Auto-detect test framework from workspace configuration.

        Args:
            language: Programming language
            workspace_path: Path to workspace

        Returns:
            Test framework name
        """
        workspace = Path(workspace_path)

        # Python: Check for pytest.ini, setup.cfg, or requirements
        if language == "python":
            if (workspace / "pytest.ini").exists():
                return "pytest"
            if (workspace / "setup.cfg").exists():
                return "pytest"
            # Default to pytest for Python
            return "pytest"

        # JavaScript/TypeScript: Check package.json
        elif language in ["javascript", "typescript"]:
            package_json = workspace / "package.json"
            if package_json.exists():
                try:
                    with open(package_json) as f:
                        data = json.load(f)
                        deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                        if "jest" in deps:
                            return "jest"
                        if "vitest" in deps:
                            return "vitest"
                        if "mocha" in deps:
                            return "mocha"
                except Exception as e:
                    logger.warning(f"Could not parse package.json: {e}")
            # Default to jest
            return "jest"

        return "pytest"  # Default fallback

    def get_test_file_path(
        self,
        source_file: str,
        language: str,
        test_framework: str
    ) -> str:
        """
        Generate appropriate test file path for source file.

        Args:
            source_file: Path to source file
            language: Programming language
            test_framework: Test framework

        Returns:
            Path to test file
        """
        source = Path(source_file)

        if language == "python":
            # Python: tests/test_<name>.py or <name>_test.py
            if test_framework == "pytest":
                # Prefer tests/ directory structure
                test_name = f"test_{source.stem}.py"
                if "backend" in str(source):
                    return f"backend/tests/{test_name}"
                return f"tests/{test_name}"
            else:  # unittest
                return str(source.parent / f"{source.stem}_test.py")

        elif language in ["javascript", "typescript"]:
            # JS/TS: <name>.test.js or <name>.spec.js
            ext = source.suffix
            if test_framework == "jest":
                return str(source.parent / f"{source.stem}.test{ext}")
            elif test_framework == "vitest":
                return str(source.parent / f"{source.stem}.test{ext}")
            else:  # mocha
                return str(source.parent / f"{source.stem}.spec{ext}")

        return f"tests/test_{source.name}"

    def read_existing_tests(self, test_file_path: str) -> Optional[str]:
        """
        Read existing tests if they exist.

        Args:
            test_file_path: Path to test file

        Returns:
            Test file content or None
        """
        try:
            if Path(test_file_path).exists():
                with open(test_file_path) as f:
                    return f.read()
        except Exception as e:
            logger.warning(f"Could not read existing tests: {e}")
        return None

    async def generate_unit_tests(
        self,
        file_path: str,
        code_content: str,
        language: Optional[str] = None,
        test_framework: Optional[str] = None,
        workspace_path: str = "/tmp/workspace",
        user_id: str = "",
        workspace_id: Optional[str] = None,
    ) -> TestFile:
        """
        Generate unit tests for a given file.

        Args:
            file_path: Path to source file
            code_content: Source code content
            language: Programming language (auto-detected if None)
            test_framework: Test framework (auto-detected if None)
            workspace_path: Path to workspace for detection
            user_id: User ID for plugin hooks
            workspace_id: Workspace ID for plugin hooks

        Returns:
            TestFile with generated tests
        """
        plugin = self._plugin

        # Plugin: check access
        if user_id and not plugin.check_access(user_id, "test_generate"):
            raise PermissionError("Insufficient credits or access denied for test generation")

        # Plugin: before_execute
        ctx = ExecutionContext(
            action="test_generate",
            user_id=user_id,
            workspace_id=workspace_id,
            metadata={"file_path": file_path},
        )
        ctx = plugin.before_execute(ctx)

        try:
            # Auto-detect language
            if not language:
                language = self.detect_language(file_path)
                if not language:
                    raise ValueError(f"Could not detect language for {file_path}")

            # Auto-detect test framework
            if not test_framework:
                test_framework = self.detect_test_framework(language, workspace_path)

            # Determine test file path
            test_file_path = self.get_test_file_path(file_path, language, test_framework)

            # Read existing tests
            existing_tests = self.read_existing_tests(test_file_path)

            # Build prompt
            prompt = self._build_unit_test_prompt(
                file_path=file_path,
                code_content=code_content,
                language=language,
                test_framework=test_framework,
                existing_tests=existing_tests
            )

            # Call Claude
            response = await self._call_claude(prompt)

            # Parse response
            test_data = self._parse_test_response(response)

            # Create TestFile
            result = TestFile(
                test_file_path=test_file_path,
                test_content=test_data["test_content"],
                tests_generated=test_data["tests_generated"],
                source_file=file_path
            )

            # Plugin: after_execute
            usage = getattr(self, "_last_usage", ExecutionUsage())
            plugin.after_execute(ctx, {"success": True, "tests_count": len(test_data["tests_generated"])}, usage)

            return result

        except Exception as e:
            plugin.on_execute_error(ctx, e)
            raise

    async def generate_regression_test(
        self,
        bug_description: str,
        fixed_files: list[str],
        fix_diff: str,
        language: str,
        test_framework: str,
        workspace_path: str = "/tmp/workspace"
    ) -> TestFile:
        """
        Generate regression test for a bug fix.

        Args:
            bug_description: Description of the bug
            fixed_files: List of files that were fixed
            fix_diff: Git diff of the fix
            language: Programming language
            test_framework: Test framework
            workspace_path: Path to workspace

        Returns:
            TestFile with regression test
        """
        # Use first fixed file as primary source
        primary_file = fixed_files[0] if fixed_files else "unknown.py"
        test_file_path = self.get_test_file_path(primary_file, language, test_framework)

        # Build prompt
        prompt = self._build_regression_test_prompt(
            bug_description=bug_description,
            fixed_files=fixed_files,
            fix_diff=fix_diff,
            language=language,
            test_framework=test_framework
        )

        # Call Claude
        response = await self._call_claude(prompt)

        # Parse response
        test_data = self._parse_test_response(response)

        return TestFile(
            test_file_path=test_file_path,
            test_content=test_data["test_content"],
            tests_generated=test_data["tests_generated"],
            source_file=primary_file
        )

    async def generate_integration_tests(
        self,
        feature_description: str,
        api_endpoints: list[dict],
        affected_files: list[str],
        language: str,
        test_framework: str,
        workspace_path: str = "/tmp/workspace"
    ) -> list[TestFile]:
        """
        Generate integration tests for a feature.

        Args:
            feature_description: Description of the feature
            api_endpoints: List of API endpoints (if applicable)
            affected_files: Files modified by the feature
            language: Programming language
            test_framework: Test framework
            workspace_path: Path to workspace

        Returns:
            List of TestFiles with integration tests
        """
        # Build prompt
        prompt = self._build_integration_test_prompt(
            feature_description=feature_description,
            api_endpoints=api_endpoints,
            affected_files=affected_files,
            language=language,
            test_framework=test_framework
        )

        # Call Claude
        response = await self._call_claude(prompt)

        # Parse response (may return multiple test files)
        test_data = self._parse_test_response(response)

        # For now, create single test file
        # In future, could generate multiple test files
        test_file_path = f"tests/integration/test_{feature_description.lower().replace(' ', '_')}.py"

        return [TestFile(
            test_file_path=test_file_path,
            test_content=test_data["test_content"],
            tests_generated=test_data["tests_generated"],
            source_file=affected_files[0] if affected_files else "unknown"
        )]

    async def _call_claude(self, prompt: str) -> str:
        """
        Call Claude API with the prompt.

        Args:
            prompt: The prompt to send to Claude

        Returns:
            Claude's response text
        """
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                temperature=0.2,  # Lower temperature for more consistent test generation
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            # Track usage for plugin lifecycle
            self._last_usage = ExecutionUsage(
                provider="anthropic",
                model=self.model,
                input_tokens=getattr(response.usage, "input_tokens", 0),
                output_tokens=getattr(response.usage, "output_tokens", 0),
                total_tokens=getattr(response.usage, "input_tokens", 0) + getattr(response.usage, "output_tokens", 0),
            )

            # Extract text from response
            if response.content and len(response.content) > 0:
                return response.content[0].text

            raise ValueError("Empty response from Claude")

        except Exception as e:
            logger.error(f"Claude API call failed: {e}")
            raise

    def _parse_test_response(self, response: str) -> dict:
        """
        Parse Claude's response to extract test content.

        Args:
            response: Claude's response text

        Returns:
            Dictionary with test_content and tests_generated
        """
        # Try to extract JSON from response
        # Claude might wrap it in markdown code blocks
        json_match = re.search(r"```json\n(.*?)\n```", response, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                return {
                    "test_content": data.get("test_content", ""),
                    "tests_generated": data.get("tests_generated", [])
                }
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON from response: {e}")

        # Fallback: Extract code from code blocks
        code_match = re.search(r"```(?:python|javascript|typescript)\n(.*?)\n```", response, re.DOTALL)
        if code_match:
            test_content = code_match.group(1)
            return {
                "test_content": test_content,
                "tests_generated": [{"test_name": "generated_test", "description": "Auto-generated test"}]
            }

        # Last resort: Return entire response as test content
        logger.warning("Could not parse structured response, using raw content")
        return {
            "test_content": response,
            "tests_generated": []
        }

    def _build_unit_test_prompt(
        self,
        file_path: str,
        code_content: str,
        language: str,
        test_framework: str,
        existing_tests: Optional[str]
    ) -> str:
        """Build prompt for unit test generation."""
        prompt = f"""You are an expert test engineer. Generate comprehensive unit tests for the following code.

**Language:** {language}
**Test Framework:** {test_framework}
**File:** {file_path}

**Code to Test:**
```{language}
{code_content}
```
"""

        if existing_tests:
            prompt += f"""
**Existing Tests:**
```{language}
{existing_tests}
```

Note: Only generate tests for code that isn't already tested. Extend the existing tests.
"""

        prompt += f"""
**Requirements:**
1. Generate tests for all public functions/methods
2. Cover normal cases, edge cases, and error cases
3. Use appropriate assertions ({self._get_assertion_style(test_framework)})
4. Follow {test_framework} best practices
5. Include setup/teardown if needed
6. Test boundary conditions
7. Mock external dependencies appropriately
8. Use clear, descriptive test names
9. Add comments explaining complex test logic

**Output Format:**
Return ONLY a JSON object with this exact structure (no additional text):
```json
{{
  "test_content": "complete test code here (properly escaped)",
  "tests_generated": [
    {{
      "test_name": "test_function_name",
      "description": "what this test covers",
      "test_type": "normal|edge|error"
    }}
  ]
}}
```

Important: The test_content should be complete, runnable test code that I can write directly to a file.
"""
        return prompt

    def _build_regression_test_prompt(
        self,
        bug_description: str,
        fixed_files: list[str],
        fix_diff: str,
        language: str,
        test_framework: str
    ) -> str:
        """Build prompt for regression test generation."""
        return f"""You are an expert test engineer. Generate a regression test that would have caught this bug.

**Bug Description:**
{bug_description}

**Fixed Files:**
{', '.join(fixed_files)}

**Fix Diff:**
```diff
{fix_diff}
```

**Language:** {language}
**Test Framework:** {test_framework}

**Requirements:**
1. Create a test that fails before the fix and passes after
2. Test the specific scenario that caused the bug
3. Include edge cases around the bug
4. Use clear test names that reference the bug
5. Add comments explaining what broke and how the test prevents regression

**Output Format:**
Return ONLY a JSON object with this exact structure:
```json
{{
  "test_content": "complete test code here",
  "tests_generated": [
    {{
      "test_name": "test_regression_<bug_summary>",
      "description": "Regression test for: {bug_description[:50]}",
      "test_type": "regression"
    }}
  ]
}}
```
"""

    def _build_integration_test_prompt(
        self,
        feature_description: str,
        api_endpoints: list[dict],
        affected_files: list[str],
        language: str,
        test_framework: str
    ) -> str:
        """Build prompt for integration test generation."""
        endpoints_str = "\n".join([
            f"- {ep.get('method', 'GET')} {ep.get('path', '')} - {ep.get('description', '')}"
            for ep in api_endpoints
        ])

        return f"""You are an expert test engineer. Generate integration tests for this feature.

**Feature Description:**
{feature_description}

**API Endpoints:**
{endpoints_str}

**Affected Files:**
{', '.join(affected_files)}

**Language:** {language}
**Test Framework:** {test_framework}

**Requirements:**
1. Test the complete feature workflow end-to-end
2. Test API endpoints with valid and invalid inputs
3. Test error handling and edge cases
4. Verify responses and side effects
5. Use appropriate test fixtures and mocks
6. Test authentication/authorization if applicable

**Output Format:**
Return ONLY a JSON object with this exact structure:
```json
{{
  "test_content": "complete integration test code",
  "tests_generated": [
    {{
      "test_name": "test_<feature>_<scenario>",
      "description": "Integration test for <scenario>",
      "test_type": "integration"
    }}
  ]
}}
```
"""

    def _get_assertion_style(self, test_framework: str) -> str:
        """Get assertion style for test framework."""
        styles = {
            "pytest": "assert statements",
            "unittest": "self.assertEqual, self.assertTrue, etc.",
            "jest": "expect().toBe(), expect().toEqual(), etc.",
            "vitest": "expect().toBe(), expect().toEqual(), etc.",
            "mocha": "chai expect() or assert()"
        }
        return styles.get(test_framework, "appropriate assertions")
