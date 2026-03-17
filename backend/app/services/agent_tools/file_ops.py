"""File operation tools for efficient code navigation."""

import ast
from pathlib import Path
from typing import Any

from .base import AgentTool, ToolContext, ToolResult


class ReadFileRangeTool(AgentTool):
    """Read specific line range from a file."""

    @property
    def name(self) -> str:
        return "read_file_range"

    @property
    def description(self) -> str:
        return """Read a specific range of lines from a file.
More efficient than reading entire file when you only need a portion.
Useful for large files or when you know the approximate location of code."""

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file relative to repository root"
                },
                "start_line": {
                    "type": "integer",
                    "description": "Starting line number (1-indexed)"
                },
                "end_line": {
                    "type": "integer",
                    "description": "Ending line number (inclusive)"
                }
            },
            "required": ["file_path", "start_line", "end_line"]
        }

    def execute(self, params: dict, context: ToolContext) -> ToolResult:
        """Execute file range read."""
        file_path = params["file_path"]
        start_line = params["start_line"]
        end_line = params["end_line"]

        # Validate line numbers
        if start_line < 1:
            return ToolResult(
                success=False,
                data={},
                error="start_line must be >= 1"
            )

        if end_line < start_line:
            return ToolResult(
                success=False,
                data={},
                error="end_line must be >= start_line"
            )

        try:
            # Safely resolve path
            full_path = self._safe_path(context, file_path)
            if not full_path:
                return ToolResult(
                    success=False,
                    data={},
                    error="Invalid file path (path traversal detected)"
                )

            if not full_path.exists():
                return ToolResult(
                    success=False,
                    data={},
                    error=f"File not found: {file_path}"
                )

            if not full_path.is_file():
                return ToolResult(
                    success=False,
                    data={},
                    error=f"Path is not a file: {file_path}"
                )

            # Read file
            with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()

            total_lines = len(lines)

            # Adjust end_line if it exceeds file length
            if end_line > total_lines:
                end_line = total_lines

            # Extract range (convert to 0-indexed)
            selected_lines = lines[start_line - 1:end_line]

            return ToolResult(
                success=True,
                data={
                    "file": file_path,
                    "start_line": start_line,
                    "end_line": end_line,
                    "total_lines": total_lines,
                    "content": "".join(selected_lines),
                    "line_count": len(selected_lines)
                }
            )

        except Exception as e:
            return ToolResult(
                success=False,
                data={},
                error=f"Failed to read file range: {str(e)}"
            )


class GetFileSymbolsTool(AgentTool):
    """Extract symbols (functions, classes, imports) from a file."""

    @property
    def name(self) -> str:
        return "get_file_symbols"

    @property
    def description(self) -> str:
        return """Extract symbols (functions, classes, imports) from a file using AST parsing.
Provides a high-level overview of file structure without reading entire content.
Works best with Python files; falls back to pattern matching for other languages."""

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file relative to repository root"
                },
                "include_docstrings": {
                    "type": "boolean",
                    "description": "Include docstrings for functions/classes (default: true)"
                },
                "include_methods": {
                    "type": "boolean",
                    "description": "Include class methods (default: true)"
                }
            },
            "required": ["file_path"]
        }

    def execute(self, params: dict, context: ToolContext) -> ToolResult:
        """Execute symbol extraction."""
        file_path = params["file_path"]
        include_docstrings = params.get("include_docstrings", True)
        include_methods = params.get("include_methods", True)

        try:
            # Safely resolve path
            full_path = self._safe_path(context, file_path)
            if not full_path:
                return ToolResult(
                    success=False,
                    data={},
                    error="Invalid file path (path traversal detected)"
                )

            if not full_path.exists():
                return ToolResult(
                    success=False,
                    data={},
                    error=f"File not found: {file_path}"
                )

            # Determine extraction method based on file type
            if full_path.suffix == '.py':
                symbols = self._extract_python_symbols(
                    full_path,
                    include_docstrings,
                    include_methods
                )
            elif full_path.suffix in {'.js', '.ts', '.jsx', '.tsx'}:
                symbols = self._extract_js_symbols(full_path)
            else:
                return ToolResult(
                    success=False,
                    data={},
                    error=f"Unsupported file type: {full_path.suffix}",
                    suggestions=[
                        "Symbol extraction currently supports: .py, .js, .ts, .jsx, .tsx",
                        "Use read_file or search_code for other file types"
                    ]
                )

            return ToolResult(
                success=True,
                data={
                    "file": file_path,
                    **symbols
                }
            )

        except Exception as e:
            return ToolResult(
                success=False,
                data={},
                error=f"Symbol extraction failed: {str(e)}"
            )

    def _extract_python_symbols(
        self,
        file_path: Path,
        include_docstrings: bool,
        include_methods: bool
    ) -> dict[str, Any]:
        """Extract symbols from Python file using AST."""
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()

        try:
            tree = ast.parse(source, filename=str(file_path))
        except SyntaxError as e:
            return {
                "error": f"Syntax error in file: {str(e)}",
                "imports": [],
                "functions": [],
                "classes": []
            }

        symbols = {
            "imports": [],
            "functions": [],
            "classes": [],
            "variables": []
        }

        # Extract top-level nodes
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    symbols["imports"].append({
                        "type": "import",
                        "name": alias.name,
                        "alias": alias.asname,
                        "line": node.lineno
                    })

            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    symbols["imports"].append({
                        "type": "from_import",
                        "module": module,
                        "name": alias.name,
                        "alias": alias.asname,
                        "line": node.lineno
                    })

            elif isinstance(node, ast.FunctionDef):
                func_info = {
                    "name": node.name,
                    "line": node.lineno,
                    "parameters": [arg.arg for arg in node.args.args],
                    "is_async": isinstance(node, ast.AsyncFunctionDef),
                    "decorators": [self._get_decorator_name(d) for d in node.decorator_list]
                }

                if include_docstrings:
                    func_info["docstring"] = ast.get_docstring(node)

                symbols["functions"].append(func_info)

            elif isinstance(node, ast.ClassDef):
                class_info = {
                    "name": node.name,
                    "line": node.lineno,
                    "bases": [self._get_node_name(base) for base in node.bases],
                    "decorators": [self._get_decorator_name(d) for d in node.decorator_list]
                }

                if include_docstrings:
                    class_info["docstring"] = ast.get_docstring(node)

                if include_methods:
                    methods = []
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef):
                            method_info = {
                                "name": item.name,
                                "line": item.lineno,
                                "parameters": [arg.arg for arg in item.args.args],
                                "is_async": isinstance(item, ast.AsyncFunctionDef)
                            }
                            if include_docstrings:
                                method_info["docstring"] = ast.get_docstring(item)
                            methods.append(method_info)
                    class_info["methods"] = methods

                symbols["classes"].append(class_info)

            elif isinstance(node, ast.Assign):
                # Top-level variable assignments
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        symbols["variables"].append({
                            "name": target.id,
                            "line": node.lineno
                        })

        return symbols

    def _extract_js_symbols(self, file_path: Path) -> dict[str, Any]:
        """Extract symbols from JavaScript/TypeScript file using basic parsing."""
        import re

        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            lines = content.split('\n')

        symbols = {
            "imports": [],
            "functions": [],
            "classes": [],
            "exports": []
        }

        # Pattern for imports
        import_pattern = re.compile(r'import\s+.*?\s+from\s+[\'"]([^\'"]+)[\'"]')
        # Pattern for functions
        func_pattern = re.compile(r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)')
        # Pattern for arrow functions
        arrow_pattern = re.compile(r'(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>')
        # Pattern for classes
        class_pattern = re.compile(r'(?:export\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?')

        for line_num, line in enumerate(lines, 1):
            # Extract imports
            for match in import_pattern.finditer(line):
                symbols["imports"].append({
                    "module": match.group(1),
                    "line": line_num
                })

            # Extract functions
            for match in func_pattern.finditer(line):
                symbols["functions"].append({
                    "name": match.group(1),
                    "parameters": [p.strip() for p in match.group(2).split(',') if p.strip()],
                    "line": line_num
                })

            # Extract arrow functions
            for match in arrow_pattern.finditer(line):
                symbols["functions"].append({
                    "name": match.group(1),
                    "type": "arrow",
                    "line": line_num
                })

            # Extract classes
            for match in class_pattern.finditer(line):
                symbols["classes"].append({
                    "name": match.group(1),
                    "extends": match.group(2),
                    "line": line_num
                })

        return symbols

    def _get_decorator_name(self, node: ast.AST) -> str:
        """Get decorator name from AST node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            return node.func.id
        return str(node)

    def _get_node_name(self, node: ast.AST) -> str:
        """Get name from AST node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_node_name(node.value)}.{node.attr}"
        return str(node)


class FindReferencesTool(AgentTool):
    """Find all references to a symbol in the codebase."""

    @property
    def name(self) -> str:
        return "find_references"

    @property
    def description(self) -> str:
        return """Find all references/usages of a function, class, or variable across the codebase.
Essential for understanding impact of changes and safe refactoring.
Returns all locations where the symbol is used."""

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "The symbol name to find references for"
                },
                "file_pattern": {
                    "type": "string",
                    "description": "Optional file pattern to limit search (e.g., '*.py')"
                },
                "include_definition": {
                    "type": "boolean",
                    "description": "Include the definition location in results (default: true)"
                }
            },
            "required": ["symbol"]
        }

    def execute(self, params: dict, context: ToolContext) -> ToolResult:
        """Execute reference search."""
        symbol = params["symbol"]
        file_pattern = params.get("file_pattern", "*")
        include_definition = params.get("include_definition", True)

        try:
            import re
            import subprocess

            # Try using ripgrep for better performance
            try:
                cmd = [
                    "rg",
                    f"\\b{re.escape(symbol)}\\b",
                    "--json",
                    "--context=1"
                ]

                if file_pattern != "*":
                    cmd.extend(["--glob", file_pattern])

                result = subprocess.run(
                    cmd,
                    cwd=context.repo_path,
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                if result.returncode <= 1:  # 0 = found, 1 = not found
                    references = self._parse_ripgrep_json(result.stdout)

                    return ToolResult(
                        success=True,
                        data={
                            "symbol": symbol,
                            "references": references,
                            "total_count": len(references)
                        }
                    )

            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass

            # Fallback to Python-based search
            references = self._search_references_python(
                context.repo_path,
                symbol,
                file_pattern
            )

            return ToolResult(
                success=True,
                data={
                    "symbol": symbol,
                    "references": references,
                    "total_count": len(references)
                }
            )

        except Exception as e:
            return ToolResult(
                success=False,
                data={},
                error=f"Reference search failed: {str(e)}"
            )

    def _parse_ripgrep_json(self, output: str) -> list[dict]:
        """Parse ripgrep JSON output."""
        import json

        references = []

        for line in output.split('\n'):
            if not line.strip():
                continue

            try:
                data = json.loads(line)

                if data.get("type") == "match":
                    match_data = data["data"]
                    references.append({
                        "file": match_data["path"]["text"],
                        "line": match_data["line_number"],
                        "content": match_data["lines"]["text"].rstrip()
                    })

            except json.JSONDecodeError:
                continue

        return references

    def _search_references_python(
        self,
        repo_path: str,
        symbol: str,
        file_pattern: str
    ) -> list[dict]:
        """Search for references using Python."""
        import re

        references = []
        repo = Path(repo_path)

        # Build search pattern (word boundary)
        pattern = re.compile(rf'\b{re.escape(symbol)}\b')

        # Determine files to search
        if file_pattern == "*":
            search_files = list(repo.glob("**/*.py")) + \
                          list(repo.glob("**/*.js")) + \
                          list(repo.glob("**/*.ts"))
        else:
            search_files = list(repo.glob(f"**/{file_pattern}"))

        for file_path in search_files[:200]:  # Limit to 200 files
            if not file_path.is_file():
                continue

            if self._should_skip_file(file_path):
                continue

            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()

                for line_num, line in enumerate(lines, 1):
                    if pattern.search(line):
                        references.append({
                            "file": str(file_path.relative_to(repo)),
                            "line": line_num,
                            "content": line.rstrip()
                        })

                        if len(references) >= 100:  # Limit results
                            return references

            except Exception:
                continue

        return references

    def _should_skip_file(self, path: Path) -> bool:
        """Check if file should be skipped."""
        skip_patterns = {
            '.git', '__pycache__', 'node_modules', '.venv', 'venv',
            'dist', 'build', '.pytest_cache'
        }

        for part in path.parts:
            if part in skip_patterns:
                return True

        return False
