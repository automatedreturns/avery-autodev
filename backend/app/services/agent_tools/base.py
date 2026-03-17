"""Base classes for agent tools."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ToolContext:
    """Context passed to tool execution."""
    repo_path: str
    branch_name: str
    workspace_id: int
    task_id: int


@dataclass
class ToolResult:
    """Result from tool execution."""
    success: bool
    data: dict[str, Any]
    error: str | None = None
    suggestions: list[str] | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary format for Claude API."""
        result = {
            "success": self.success,
            **self.data
        }
        if self.error:
            result["error"] = self.error
        if self.suggestions:
            result["suggestions"] = self.suggestions
        return result


class AgentTool(ABC):
    """Base class for all agent tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name for Claude API."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Tool description for Claude API."""
        pass

    @property
    @abstractmethod
    def input_schema(self) -> dict:
        """Input schema for Claude API."""
        pass

    def to_anthropic_format(self) -> dict:
        """Convert tool to Anthropic API format."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema
        }

    @abstractmethod
    def execute(self, params: dict, context: ToolContext) -> ToolResult:
        """Execute the tool with given parameters."""
        pass

    def validate_params(self, params: dict) -> tuple[bool, str | None]:
        """
        Validate input parameters.

        Returns:
            (is_valid, error_message)
        """
        required = self.input_schema.get("required", [])
        for field in required:
            if field not in params:
                return False, f"Missing required parameter: {field}"
        return True, None

    def _safe_path(self, context: ToolContext, relative_path: str) -> Path | None:
        """
        Safely resolve a path within the repository.

        Returns:
            Path object if valid, None if path traversal detected
        """
        repo = Path(context.repo_path).resolve()
        target = (repo / relative_path).resolve()

        try:
            target.relative_to(repo)
            return target
        except ValueError:
            # Path traversal detected
            return None
