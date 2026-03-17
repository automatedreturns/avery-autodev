"""Agent tool registry for managing and executing tools."""

from typing import Type

from .base import AgentTool, ToolContext, ToolResult


class AgentToolRegistry:
    """Registry for managing agent tools."""

    def __init__(self):
        self._tools: dict[str, AgentTool] = {}

    def register(self, tool: AgentTool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool

    def register_class(self, tool_class: Type[AgentTool]) -> None:
        """Register a tool class (instantiates it)."""
        tool = tool_class()
        self.register(tool)

    def get_tool_definitions(self) -> list[dict]:
        """Get all tool definitions in Anthropic API format."""
        return [tool.to_anthropic_format() for tool in self._tools.values()]

    def execute_tool(self, name: str, params: dict, context: ToolContext) -> ToolResult:
        """
        Execute a tool by name.

        Args:
            name: Tool name
            params: Tool parameters
            context: Execution context

        Returns:
            ToolResult with execution result

        Raises:
            ValueError: If tool not found
        """
        if name not in self._tools:
            return ToolResult(
                success=False,
                data={},
                error=f"Unknown tool: {name}"
            )

        tool = self._tools[name]

        # Validate parameters
        is_valid, error = tool.validate_params(params)
        if not is_valid:
            return ToolResult(
                success=False,
                data={},
                error=error
            )

        # Execute tool
        try:
            return tool.execute(params, context)
        except Exception as e:
            return ToolResult(
                success=False,
                data={},
                error=f"Tool execution failed: {str(e)}"
            )

    def has_tool(self, name: str) -> bool:
        """Check if tool is registered."""
        return name in self._tools

    def get_tool(self, name: str) -> AgentTool | None:
        """Get tool by name."""
        return self._tools.get(name)
