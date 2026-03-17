"""Manager for agent tools - handles tool registration and execution."""

from pathlib import Path

from .agent_tools import (
    AgentToolRegistry,
    ToolContext,
    SearchCodeTool,
    FindDefinitionTool,
    RunTestsTool,
    RunBuildTool,
    RunLinterTool,
    TypeCheckTool,
    GetGitDiffTool,
    GitStatusTool,
    InstallDependenciesTool,
    CheckDependenciesTool,
    ReadFileRangeTool,
    GetFileSymbolsTool,
    FindReferencesTool
)
from .agent_tools.validation_pipeline import ValidationPipeline
from . import git_local_service


class AgentToolManager:
    """Manages agent tools and provides execution interface."""

    def __init__(self):
        self.registry = AgentToolRegistry()
        self._register_all_tools()

    def _register_all_tools(self):
        """Register all available tools."""
        # Phase 1 tools
        self.registry.register_class(SearchCodeTool)
        self.registry.register_class(FindDefinitionTool)
        self.registry.register_class(RunTestsTool)
        self.registry.register_class(RunBuildTool)
        self.registry.register_class(RunLinterTool)
        self.registry.register_class(TypeCheckTool)
        self.registry.register_class(GetGitDiffTool)
        self.registry.register_class(GitStatusTool)
        self.registry.register_class(InstallDependenciesTool)
        self.registry.register_class(CheckDependenciesTool)

        # Phase 2 tools
        self.registry.register_class(ReadFileRangeTool)
        self.registry.register_class(GetFileSymbolsTool)
        self.registry.register_class(FindReferencesTool)

    def get_legacy_tools(self) -> list[dict]:
        """
        Get legacy tool definitions (read_file, write_file, list_directory, request_user_input).

        These are handled separately for backwards compatibility.
        """
        return [
            {
                "name": "read_file",
                "description": "Read the contents of a file from the repository. Use this when you need to see existing code.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "The path to the file relative to repository root (e.g., 'src/main.py')"
                        }
                    },
                    "required": ["file_path"]
                }
            },
            {
                "name": "write_file",
                "description": "Write or update a file in the repository. Use this to implement changes. Provide the complete file content.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "The path to the file relative to repository root"
                        },
                        "content": {
                            "type": "string",
                            "description": "The complete content of the file"
                        },
                        "commit_message": {
                            "type": "string",
                            "description": "A brief commit message describing the change"
                        }
                    },
                    "required": ["file_path", "content", "commit_message"]
                }
            },
            {
                "name": "list_directory",
                "description": "List files in a directory. Use this to explore the codebase structure.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "directory_path": {
                            "type": "string",
                            "description": "The directory path (e.g., 'src' or 'src/components'). Use empty string for root."
                        }
                    },
                    "required": ["directory_path"]
                }
            },
            {
                "name": "request_user_input",
                "description": "Request input or confirmation from the user when you need their decision before proceeding. Use this when you need the user to choose between options, confirm an action, or provide specific input.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "message": {
                            "type": "string",
                            "description": "The question or prompt to show the user"
                        },
                        "input_type": {
                            "type": "string",
                            "enum": ["choice", "confirm", "text"],
                            "description": "Type of input: 'choice' for multiple options, 'confirm' for yes/no, 'text' for free-form input"
                        },
                        "options": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Available options for 'choice' type (e.g., ['Option A', 'Option B']). Not required for 'confirm' or 'text' types."
                        }
                    },
                    "required": ["message", "input_type"]
                }
            }
        ]

    def get_all_tool_definitions(self) -> list[dict]:
        """Get all tool definitions for Claude API."""
        return self.get_legacy_tools() + self.registry.get_tool_definitions()

    def execute_tool(
        self,
        tool_name: str,
        tool_input: dict,
        repo_path: str,
        branch_name: str,
        workspace_id: int,
        task_id: int
    ) -> dict:
        """
        Execute a tool (handles both legacy and new tools).

        Args:
            tool_name: Name of the tool
            tool_input: Tool input parameters
            repo_path: Repository path
            branch_name: Current branch name
            workspace_id: Workspace ID
            task_id: Task ID

        Returns:
            Tool result as dict
        """
        # Check if it's a legacy tool (handled separately)
        if tool_name in ("read_file", "write_file", "list_directory", "request_user_input"):
            return None  # Handled by existing code

        # Execute new tool
        context = ToolContext(
            repo_path=repo_path,
            branch_name=branch_name,
            workspace_id=workspace_id,
            task_id=task_id
        )

        result = self.registry.execute_tool(tool_name, tool_input, context)
        return result.to_dict()

    def create_validation_pipeline(
        self,
        repo_path: str,
        branch_name: str,
        workspace_id: int,
        task_id: int
    ) -> ValidationPipeline:
        """Create a validation pipeline for the given context."""
        context = ToolContext(
            repo_path=repo_path,
            branch_name=branch_name,
            workspace_id=workspace_id,
            task_id=task_id
        )
        return ValidationPipeline(context)


# Global instance
_tool_manager = None


def get_tool_manager() -> AgentToolManager:
    """Get or create the global tool manager instance."""
    global _tool_manager
    if _tool_manager is None:
        _tool_manager = AgentToolManager()
    return _tool_manager
