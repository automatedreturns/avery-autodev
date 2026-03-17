"""Code search and navigation tools."""

import ast
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from .base import AgentTool, ToolContext, ToolResult


class SearchCodeTool(AgentTool):
    """Search for code patterns across the repository."""

    @property
    def name(self) -> str:
        return "search_code"

    @property
    def description(self) -> str:
        return """Search for code patterns across the repository using regex or literal strings.
Use this to find where functions, classes, or specific code patterns are used.
Returns matching lines with context."""

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Search pattern (supports regex)"
                },
                "file_pattern": {
                    "type": "string",
                    "description": "File glob pattern to limit search (e.g., '*.py', 'src/**/*.js'). Optional."
                },
                "case_sensitive": {
                    "type": "boolean",
                    "description": "Whether search should be case-sensitive (default: false)"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default: 100)"
                },
                "context_lines": {
                    "type": "integer",
                    "description": "Number of context lines before and after match (default: 2)"
                }
            },
            "required": ["pattern"]
        }

    def execute(self, params: dict, context: ToolContext) -> ToolResult:
        """Execute code search."""
        pattern = params["pattern"]
        file_pattern = params.get("file_pattern", "*")
        case_sensitive = params.get("case_sensitive", False)
        max_results = params.get("max_results", 100)
        context_lines = params.get("context_lines", 2)

        try:
            # Try using ripgrep first (much faster)
            matches = self._search_with_ripgrep(
                context.repo_path,
                pattern,
                file_pattern,
                case_sensitive,
                max_results,
                context_lines
            )

            if matches is None:
                # Fallback to git grep
                matches = self._search_with_git_grep(
                    context.repo_path,
                    pattern,
                    file_pattern,
                    case_sensitive,
                    max_results,
                    context_lines
                )

            if matches is None:
                # Fallback to Python search
                matches = self._search_with_python(
                    context.repo_path,
                    pattern,
                    file_pattern,
                    case_sensitive,
                    max_results
                )

            return ToolResult(
                success=True,
                data={
                    "matches": matches[:max_results],
                    "total_matches": len(matches),
                    "truncated": len(matches) > max_results
                }
            )

        except Exception as e:
            return ToolResult(
                success=False,
                data={},
                error=f"Search failed: {str(e)}"
            )

    def _search_with_ripgrep(
        self,
        repo_path: str,
        pattern: str,
        file_pattern: str,
        case_sensitive: bool,
        max_results: int,
        context_lines: int
    ) -> list[dict] | None:
        """Search using ripgrep (rg)."""
        try:
            cmd = [
                "rg",
                pattern,
                "--json",
                f"--context={context_lines}",
                f"--max-count={max_results}",
                "--heading",
                "--line-number"
            ]

            if not case_sensitive:
                cmd.append("-i")

            if file_pattern != "*":
                cmd.extend(["--glob", file_pattern])

            result = subprocess.run(
                cmd,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode > 1:  # 0 = found, 1 = not found, >1 = error
                return None

            return self._parse_ripgrep_json(result.stdout)

        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None

    def _search_with_git_grep(
        self,
        repo_path: str,
        pattern: str,
        file_pattern: str,
        case_sensitive: bool,
        max_results: int,
        context_lines: int
    ) -> list[dict] | None:
        """Search using git grep."""
        try:
            cmd = ["git", "grep", "-n", f"-C{context_lines}"]

            if not case_sensitive:
                cmd.append("-i")

            cmd.append(pattern)

            if file_pattern != "*":
                cmd.append("--")
                cmd.append(file_pattern)

            result = subprocess.run(
                cmd,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode > 1:
                return None

            return self._parse_grep_output(result.stdout, max_results)

        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None

    def _search_with_python(
        self,
        repo_path: str,
        pattern: str,
        file_pattern: str,
        case_sensitive: bool,
        max_results: int
    ) -> list[dict]:
        """Fallback: search using Python."""
        matches = []
        repo = Path(repo_path)

        # Convert glob pattern
        if file_pattern == "*":
            file_pattern = "**/*"

        # Compile regex
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            regex = re.compile(pattern, flags)
        except re.error:
            # If regex is invalid, use literal search
            regex = re.compile(re.escape(pattern), flags)

        for file_path in repo.glob(file_pattern):
            if not file_path.is_file():
                continue

            # Skip binary files and common excludes
            if self._should_skip_file(file_path):
                continue

            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()

                for line_num, line in enumerate(lines, 1):
                    if regex.search(line):
                        matches.append({
                            "file": str(file_path.relative_to(repo)),
                            "line": line_num,
                            "column": 0,
                            "content": line.rstrip()
                        })

                        if len(matches) >= max_results:
                            return matches

            except Exception:
                continue

        return matches

    def _parse_ripgrep_json(self, output: str) -> list[dict]:
        """Parse ripgrep JSON output."""
        matches = []

        for line in output.split('\n'):
            if not line.strip():
                continue

            try:
                data = json.loads(line)

                if data.get("type") == "match":
                    match_data = data["data"]
                    matches.append({
                        "file": match_data["path"]["text"],
                        "line": match_data["line_number"],
                        "column": match_data["submatches"][0]["start"] if match_data.get("submatches") else 0,
                        "content": match_data["lines"]["text"].rstrip()
                    })

            except json.JSONDecodeError:
                continue

        return matches

    def _parse_grep_output(self, output: str, max_results: int) -> list[dict]:
        """Parse git grep output."""
        matches = []

        for line in output.split('\n'):
            if not line.strip() or line.startswith('--'):
                continue

            # Format: file:line:content
            parts = line.split(':', 2)
            if len(parts) >= 3:
                matches.append({
                    "file": parts[0],
                    "line": int(parts[1]) if parts[1].isdigit() else 0,
                    "column": 0,
                    "content": parts[2].rstrip()
                })

                if len(matches) >= max_results:
                    break

        return matches

    def _should_skip_file(self, path: Path) -> bool:
        """Check if file should be skipped."""
        skip_patterns = {
            '.git', '__pycache__', 'node_modules', '.venv', 'venv',
            'dist', 'build', '.pytest_cache', '.eggs', '*.pyc'
        }

        for part in path.parts:
            if part in skip_patterns:
                return True

        if path.suffix in {'.pyc', '.pyo', '.so', '.dylib', '.dll'}:
            return True

        return False


class FindDefinitionTool(AgentTool):
    """Find the definition of a function, class, or variable."""

    @property
    def name(self) -> str:
        return "find_definition"

    @property
    def description(self) -> str:
        return """Find the definition of a function, class, or variable in the codebase.
Uses AST parsing for Python and pattern matching for other languages.
Returns the file, line number, and definition context."""

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "The function/class/variable name to find"
                },
                "file_hint": {
                    "type": "string",
                    "description": "Optional file path hint to narrow search"
                },
                "symbol_type": {
                    "type": "string",
                    "enum": ["function", "class", "variable", "any"],
                    "description": "Type of symbol to find (default: any)"
                }
            },
            "required": ["symbol"]
        }

    def execute(self, params: dict, context: ToolContext) -> ToolResult:
        """Execute definition search."""
        symbol = params["symbol"]
        file_hint = params.get("file_hint")
        symbol_type = params.get("symbol_type", "any")

        try:
            definitions = []
            repo = Path(context.repo_path)

            # Determine search paths
            if file_hint:
                search_paths = [repo / file_hint]
            else:
                # Search Python files first, then JavaScript/TypeScript
                search_paths = list(repo.glob("**/*.py")) + \
                              list(repo.glob("**/*.js")) + \
                              list(repo.glob("**/*.ts")) + \
                              list(repo.glob("**/*.tsx"))

            for file_path in search_paths:
                if not file_path.is_file():
                    continue

                if self._should_skip_file(file_path):
                    continue

                file_defs = self._find_in_file(file_path, symbol, symbol_type, repo)
                definitions.extend(file_defs)

            if not definitions:
                return ToolResult(
                    success=True,
                    data={
                        "found": False,
                        "definitions": []
                    },
                    suggestions=[
                        f"Symbol '{symbol}' not found",
                        "Try searching with a different name or check spelling",
                        "The symbol might be imported from an external library"
                    ]
                )

            return ToolResult(
                success=True,
                data={
                    "found": True,
                    "definitions": definitions
                }
            )

        except Exception as e:
            return ToolResult(
                success=False,
                data={},
                error=f"Definition search failed: {str(e)}"
            )

    def _find_in_file(
        self,
        file_path: Path,
        symbol: str,
        symbol_type: str,
        repo_root: Path
    ) -> list[dict]:
        """Find definitions in a single file."""
        definitions = []

        if file_path.suffix == '.py':
            definitions = self._find_python_definitions(file_path, symbol, symbol_type, repo_root)
        else:
            definitions = self._find_with_patterns(file_path, symbol, symbol_type, repo_root)

        return definitions

    def _find_python_definitions(
        self,
        file_path: Path,
        symbol: str,
        symbol_type: str,
        repo_root: Path
    ) -> list[dict]:
        """Find definitions in Python files using AST."""
        definitions = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()

            tree = ast.parse(source, filename=str(file_path))

            for node in ast.walk(tree):
                definition = None

                if symbol_type in ("function", "any") and isinstance(node, ast.FunctionDef):
                    if node.name == symbol:
                        definition = {
                            "type": "function",
                            "name": node.name,
                            "line": node.lineno,
                            "file": str(file_path.relative_to(repo_root)),
                            "signature": self._get_function_signature(node),
                            "docstring": ast.get_docstring(node)
                        }

                elif symbol_type in ("class", "any") and isinstance(node, ast.ClassDef):
                    if node.name == symbol:
                        definition = {
                            "type": "class",
                            "name": node.name,
                            "line": node.lineno,
                            "file": str(file_path.relative_to(repo_root)),
                            "bases": [self._get_node_name(base) for base in node.bases],
                            "docstring": ast.get_docstring(node)
                        }

                if definition:
                    definitions.append(definition)

        except Exception:
            pass

        return definitions

    def _find_with_patterns(
        self,
        file_path: Path,
        symbol: str,
        symbol_type: str,
        repo_root: Path
    ) -> list[dict]:
        """Find definitions using regex patterns."""
        definitions = []

        # Patterns for different languages
        patterns = {
            "function": [
                rf"function\s+{re.escape(symbol)}\s*\(",  # JavaScript
                rf"const\s+{re.escape(symbol)}\s*=\s*\([^)]*\)\s*=>",  # Arrow function
                rf"def\s+{re.escape(symbol)}\s*\(",  # Python (fallback)
            ],
            "class": [
                rf"class\s+{re.escape(symbol)}\s*[{{:]",  # JS/Python
            ]
        }

        if symbol_type == "any":
            search_patterns = patterns["function"] + patterns["class"]
        else:
            search_patterns = patterns.get(symbol_type, [])

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            for line_num, line in enumerate(lines, 1):
                for pattern in search_patterns:
                    if re.search(pattern, line):
                        definitions.append({
                            "type": symbol_type,
                            "name": symbol,
                            "line": line_num,
                            "file": str(file_path.relative_to(repo_root)),
                            "content": line.strip()
                        })
                        break

        except Exception:
            pass

        return definitions

    def _get_function_signature(self, node: ast.FunctionDef) -> str:
        """Get function signature from AST node."""
        args = []
        for arg in node.args.args:
            args.append(arg.arg)

        return f"{node.name}({', '.join(args)})"

    def _get_node_name(self, node: ast.AST) -> str:
        """Get name from AST node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_node_name(node.value)}.{node.attr}"
        return str(node)

    def _should_skip_file(self, path: Path) -> bool:
        """Check if file should be skipped."""
        skip_patterns = {
            '.git', '__pycache__', 'node_modules', '.venv', 'venv',
            'dist', 'build', '.pytest_cache', '.eggs'
        }

        for part in path.parts:
            if part in skip_patterns:
                return True

        return False
