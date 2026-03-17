"""MCP server for AgentToolManager tools."""

import asyncio
import json
import logging
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .agent_tool_manager import get_tool_manager
from .agent_tools import ToolContext

logger = logging.getLogger(__name__)


class AgentToolMCPServer:
    """MCP server that exposes AgentToolManager tools."""

    def __init__(self):
        self.server = Server("agent-tools")
        self.tool_manager = get_tool_manager()
        self._setup_handlers()

    def _setup_handlers(self):
        """Set up MCP server handlers."""

        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            """List all available tools from AgentToolManager."""
            tool_definitions = self.tool_manager.get_all_tool_definitions()

            mcp_tools = []
            for tool_def in tool_definitions:
                mcp_tool = Tool(
                    name=tool_def["name"],
                    description=tool_def["description"],
                    inputSchema=tool_def["input_schema"]
                )
                mcp_tools.append(mcp_tool)

            logger.info(f"Listed {len(mcp_tools)} tools")
            return mcp_tools

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
            """Execute a tool from AgentToolManager."""
            logger.info(f"Calling tool: {name} with arguments: {arguments}")

            try:
                # Extract context from environment variables
                import os
                repo_path = os.getenv("repo_path", os.getcwd())
                branch_name = os.getenv("branch", "main")
                workspace_id = int(os.getenv("workspace_id", "0"))
                task_id = int(os.getenv("task_id", "0"))

                # Execute the tool
                result = self.tool_manager.execute_tool(
                    tool_name=name,
                    tool_input=arguments,
                    repo_path=repo_path,
                    branch_name=branch_name,
                    workspace_id=workspace_id,
                    task_id=task_id
                )

                # Handle legacy tools (return None)
                if result is None:
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "error": f"Tool {name} is a legacy tool and must be handled separately"
                        })
                    )]

                # Return the result as JSON
                return [TextContent(
                    type="text",
                    text=json.dumps(result, indent=2)
                )]

            except Exception as e:
                logger.error(f"Error executing tool {name}: {str(e)}", exc_info=True)
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "success": False,
                        "error": str(e)
                    })
                )]

    async def run(self):
        """Run the MCP server."""
        async with stdio_server() as (read_stream, write_stream):
            logger.info("Starting Agent Tools MCP server")
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options()
            )


async def main():
    """Main entry point for the MCP server."""
    logging.basicConfig(level=logging.INFO)
    server = AgentToolMCPServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
