"""Test Quality Validator - Validates generated tests meet quality standards."""

import ast
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of test validation."""
    passed: bool
    quality_score: float  # 0-100
    checks: dict[str, bool]
    issues: list[str]
    suggestions: list[str]

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "quality_score": self.quality_score,
            "checks": self.checks,
            "issues": self.issues,
            "suggestions": self.suggestions
        }


class TestQualityValidator:
    """Validate generated tests meet quality standards."""

    # Minimum scores for each check (0-100)
    MIN_SCORES = {
        "syntax_valid": 100,  # Must be 100
        "imports_present": 80,
        "assertions_present": 100,  # Must be 100
        "edge_cases_covered": 60,
        "descriptive_names": 70,
        "documentation_present": 50,
    }

    # Minimum overall quality score to pass
    MIN_QUALITY_SCORE = 70.0

    def __init__(self):
        """Initialize validator."""
        self.issues = []
        self.suggestions = []

    def validate_test_file(
        self,
        test_file_path: str,
        test_content: str,
        language: str
    ) -> ValidationResult:
        """
        Comprehensive validation of a test file.

        Args:
            test_file_path: Path to test file
            test_content: Content of test file
            language: Programming language

        Returns:
            ValidationResult with score and details
        """
        self.issues = []
        self.suggestions = []

        # Run all checks based on language
        if language == "python":
            checks = self._validate_python_test(test_file_path, test_content)
        elif language in ["javascript", "typescript"]:
            checks = self._validate_js_test(test_file_path, test_content, language)
        else:
            # Unknown language - basic validation
            checks = self._validate_generic_test(test_content)

        # Calculate overall quality score
        quality_score = self._calculate_quality_score(checks)

        # Determine if validation passed
        passed = (
            quality_score >= self.MIN_QUALITY_SCORE and
            checks.get("syntax_valid", False) and
            checks.get("assertions_present", False)
        )

        return ValidationResult(
            passed=passed,
            quality_score=quality_score,
            checks=checks,
            issues=self.issues,
            suggestions=self.suggestions
        )

    def _validate_python_test(self, test_file_path: str, test_content: str) -> dict[str, bool]:
        """Validate Python test file."""
        checks = {}

        # 1. Syntax validation
        checks["syntax_valid"] = self._check_python_syntax(test_content)

        # 2. Imports present
        checks["imports_present"] = self._check_python_imports(test_content)

        # 3. Assertions present
        checks["assertions_present"] = self._check_python_assertions(test_content)

        # 4. Edge cases covered
        checks["edge_cases_covered"] = self._check_edge_cases_python(test_content)

        # 5. Descriptive names
        checks["descriptive_names"] = self._check_descriptive_names_python(test_content)

        # 6. Documentation present
        checks["documentation_present"] = self._check_python_documentation(test_content)

        return checks

    def _validate_js_test(self, test_file_path: str, test_content: str, language: str) -> dict[str, bool]:
        """Validate JavaScript/TypeScript test file."""
        checks = {}

        # 1. Syntax validation (basic - can't fully validate without parser)
        checks["syntax_valid"] = self._check_js_syntax_basic(test_content)

        # 2. Imports present
        checks["imports_present"] = self._check_js_imports(test_content)

        # 3. Assertions present
        checks["assertions_present"] = self._check_js_assertions(test_content)

        # 4. Edge cases covered
        checks["edge_cases_covered"] = self._check_edge_cases_js(test_content)

        # 5. Descriptive names
        checks["descriptive_names"] = self._check_descriptive_names_js(test_content)

        # 6. Documentation present
        checks["documentation_present"] = self._check_js_documentation(test_content)

        return checks

    def _validate_generic_test(self, test_content: str) -> dict[str, bool]:
        """Generic validation for unknown languages."""
        return {
            "syntax_valid": len(test_content) > 0,
            "imports_present": True,  # Can't check
            "assertions_present": self._check_generic_assertions(test_content),
            "edge_cases_covered": True,  # Can't check
            "descriptive_names": True,  # Can't check
            "documentation_present": self._check_generic_documentation(test_content)
        }

    # Python-specific checks

    def _check_python_syntax(self, code: str) -> bool:
        """Check if Python code has valid syntax."""
        try:
            ast.parse(code)
            return True
        except SyntaxError as e:
            self.issues.append(f"Syntax error: {e.msg} at line {e.lineno}")
            return False
        except Exception as e:
            self.issues.append(f"Syntax validation error: {str(e)}")
            return False

    def _check_python_imports(self, code: str) -> bool:
        """Check if Python test has necessary imports."""
        # Check for test framework import
        has_pytest = "import pytest" in code or "from pytest" in code
        has_unittest = "import unittest" in code or "from unittest" in code

        if not (has_pytest or has_unittest):
            self.issues.append("Missing test framework import (pytest or unittest)")
            return False

        # Check for common testing utilities
        has_mock = "mock" in code.lower() or "patch" in code

        if not has_mock and ("def test_" in code or "class Test" in code):
            self.suggestions.append("Consider using mocks for external dependencies")

        return True

    def _check_python_assertions(self, code: str) -> bool:
        """Check if Python test has assertions."""
        # pytest style: assert statements
        has_assert = re.search(r'\bassert\s+', code)

        # unittest style: self.assertEqual, self.assertTrue, etc.
        has_unittest_assert = re.search(r'self\.assert\w+\(', code)

        if not (has_assert or has_unittest_assert):
            self.issues.append("No assertions found in test code")
            return False

        # Count assertions
        assert_count = len(re.findall(r'\bassert\s+', code))
        assert_count += len(re.findall(r'self\.assert\w+\(', code))

        if assert_count < 1:
            self.issues.append("Insufficient assertions (need at least 1)")
            return False

        return True

    def _check_edge_cases_python(self, code: str) -> bool:
        """Check if Python test covers edge cases."""
        edge_case_indicators = [
            r'empty',
            r'none',
            r'null',
            r'zero',
            r'negative',
            r'boundary',
            r'edge',
            r'invalid',
            r'error',
            r'exception',
            r'raises',
            r'with pytest\.raises',
        ]

        code_lower = code.lower()
        edge_cases_found = sum(
            1 for indicator in edge_case_indicators
            if re.search(indicator, code_lower)
        )

        if edge_cases_found == 0:
            self.suggestions.append("Consider adding tests for edge cases (empty input, None, boundaries, etc.)")
            return False
        elif edge_cases_found < 2:
            self.suggestions.append("Consider adding more edge case coverage")

        return edge_cases_found >= 1

    def _check_descriptive_names_python(self, code: str) -> bool:
        """Check if Python test functions have descriptive names."""
        # Extract test function names
        test_functions = re.findall(r'def (test_\w+)\(', code)

        if not test_functions:
            self.issues.append("No test functions found")
            return False

        # Check name quality
        short_names = [name for name in test_functions if len(name) < 10]
        generic_names = [name for name in test_functions if re.match(r'test_[0-9]+$', name)]

        if len(short_names) > len(test_functions) * 0.5:
            self.suggestions.append("Use more descriptive test names (e.g., test_user_login_with_invalid_password)")

        if generic_names:
            self.issues.append(f"Avoid generic test names like: {', '.join(generic_names)}")
            return False

        return True

    def _check_python_documentation(self, code: str) -> bool:
        """Check if Python test has documentation."""
        # Check for docstrings
        has_docstrings = '"""' in code or "'''" in code

        # Check for comments
        has_comments = "#" in code

        if not (has_docstrings or has_comments):
            self.suggestions.append("Add comments or docstrings to explain complex test logic")
            return False

        return True

    # JavaScript/TypeScript-specific checks

    def _check_js_syntax_basic(self, code: str) -> bool:
        """Basic JavaScript/TypeScript syntax check."""
        # Very basic checks (proper validation would need a parser)
        # Check for balanced braces
        open_braces = code.count('{')
        close_braces = code.count('}')

        if open_braces != close_braces:
            self.issues.append("Unbalanced braces - possible syntax error")
            return False

        # Check for balanced parentheses
        open_parens = code.count('(')
        close_parens = code.count(')')

        if open_parens != close_parens:
            self.issues.append("Unbalanced parentheses - possible syntax error")
            return False

        return True

    def _check_js_imports(self, code: str) -> bool:
        """Check if JS/TS test has necessary imports."""
        # Check for test framework
        has_jest = "import" in code and ("jest" in code or "@jest" in code)
        has_vitest = "import" in code and ("vitest" in code or "@vitest" in code)
        has_mocha = "import" in code and ("mocha" in code or "chai" in code)
        has_describe = "describe" in code
        has_test_or_it = "test(" in code or "it(" in code

        if not (has_jest or has_vitest or has_mocha or has_describe or has_test_or_it):
            self.issues.append("Missing test framework setup")
            return False

        return True

    def _check_js_assertions(self, code: str) -> bool:
        """Check if JS/TS test has assertions."""
        # Check for expect() statements
        has_expect = re.search(r'expect\(', code)

        # Check for assert statements
        has_assert = re.search(r'assert\(', code)

        if not (has_expect or has_assert):
            self.issues.append("No assertions found (expect() or assert())")
            return False

        # Count assertions
        assertion_count = len(re.findall(r'expect\(', code))
        assertion_count += len(re.findall(r'assert\(', code))

        if assertion_count < 1:
            self.issues.append("Insufficient assertions")
            return False

        return True

    def _check_edge_cases_js(self, code: str) -> bool:
        """Check if JS/TS test covers edge cases."""
        edge_case_indicators = [
            r'empty',
            r'null',
            r'undefined',
            r'zero',
            r'negative',
            r'boundary',
            r'edge',
            r'invalid',
            r'error',
            r'throws',
            r'toThrow',
            r'rejects',
        ]

        code_lower = code.lower()
        edge_cases_found = sum(
            1 for indicator in edge_case_indicators
            if re.search(indicator, code_lower)
        )

        if edge_cases_found == 0:
            self.suggestions.append("Consider adding tests for edge cases (null, undefined, empty, etc.)")
            return False
        elif edge_cases_found < 2:
            self.suggestions.append("Consider adding more edge case coverage")

        return edge_cases_found >= 1

    def _check_descriptive_names_js(self, code: str) -> bool:
        """Check if JS/TS test has descriptive names."""
        # Extract test names from describe() and test()/it() blocks
        test_names = re.findall(r'(?:test|it)\([\'"](.+?)[\'"]', code)

        if not test_names:
            self.issues.append("No test cases found")
            return False

        # Check for generic names
        generic_names = [name for name in test_names if name in ["test", "it works", "test 1"]]

        if generic_names:
            self.issues.append("Avoid generic test names - be specific about what you're testing")
            return False

        return True

    def _check_js_documentation(self, code: str) -> bool:
        """Check if JS/TS test has documentation."""
        # Check for comments
        has_line_comments = "//" in code
        has_block_comments = "/*" in code and "*/" in code

        if not (has_line_comments or has_block_comments):
            self.suggestions.append("Add comments to explain complex test logic")
            return False

        return True

    # Generic checks

    def _check_generic_assertions(self, code: str) -> bool:
        """Generic assertion check for unknown languages."""
        assertion_keywords = ["assert", "expect", "should", "verify", "check"]
        code_lower = code.lower()

        return any(keyword in code_lower for keyword in assertion_keywords)

    def _check_generic_documentation(self, code: str) -> bool:
        """Generic documentation check."""
        comment_indicators = ["#", "//", "/*", "\"\"\"", "'''"]
        return any(indicator in code for indicator in comment_indicators)

    # Quality score calculation

    def _calculate_quality_score(self, checks: dict[str, bool]) -> float:
        """
        Calculate overall quality score (0-100).

        Args:
            checks: Dictionary of check results

        Returns:
            Quality score 0-100
        """
        if not checks:
            return 0.0

        # Weighted scoring
        weights = {
            "syntax_valid": 30.0,  # Critical
            "assertions_present": 30.0,  # Critical
            "imports_present": 10.0,
            "edge_cases_covered": 15.0,
            "descriptive_names": 10.0,
            "documentation_present": 5.0,
        }

        total_weight = sum(weights.values())
        score = 0.0

        for check_name, passed in checks.items():
            if check_name in weights:
                if passed:
                    score += weights[check_name]

        # Normalize to 0-100
        return (score / total_weight) * 100 if total_weight > 0 else 0.0

    # Utility methods

    def get_quality_grade(self, score: float) -> str:
        """Get letter grade for quality score."""
        if score >= 90:
            return "A"
        elif score >= 80:
            return "B"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        else:
            return "F"

    def generate_quality_report(self, validation_result: ValidationResult) -> str:
        """Generate human-readable quality report."""
        grade = self.get_quality_grade(validation_result.quality_score)

        report = f"""
Test Quality Report
==================
Overall Score: {validation_result.quality_score:.1f}/100 (Grade: {grade})
Status: {'✓ PASSED' if validation_result.passed else '✗ FAILED'}

Checks:
"""
        for check_name, passed in validation_result.checks.items():
            status = "✓" if passed else "✗"
            report += f"  {status} {check_name.replace('_', ' ').title()}\n"

        if validation_result.issues:
            report += "\nIssues:\n"
            for issue in validation_result.issues:
                report += f"  ❌ {issue}\n"

        if validation_result.suggestions:
            report += "\nSuggestions:\n"
            for suggestion in validation_result.suggestions:
                report += f"  💡 {suggestion}\n"

        return report
