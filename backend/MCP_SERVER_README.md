# Agent Tools MCP Server

This MCP (Model Context Protocol) server exposes the AgentToolManager tools to Claude Agent SDK, enabling advanced code analysis, validation, and development operations.

## Overview

The MCP server provides access to all AgentToolManager tools through the Model Context Protocol, allowing the Claude Agent SDK to use these tools during task execution.

## Available Tools

### Code Search & Navigation
- **search_code**: Search code patterns across the repository using regex or literal strings
- **find_definition**: Find function/class/variable definitions using AST parsing for Python
- **find_references**: Find all references/usages of a symbol across the codebase

### Validation & Quality
- **run_tests**: Execute project tests (pytest, jest, mocha, unittest)
- **run_build**: Build the project (npm, TypeScript, Python)
- **run_linter**: Run code linters (ESLint, flake8, black, prettier)
- **type_check**: Type checking (TypeScript, mypy, pyright)

### Git Operations
- **get_git_diff**: View git diff of changes in working directory
- **git_status**: Get current git repository status

### Dependencies
- **install_dependencies**: Install or update project dependencies (npm/pip)
- **check_dependencies**: Check for outdated or vulnerable dependencies

### File Operations
- **read_file_range**: Read specific line ranges from files efficiently
- **get_file_symbols**: Extract symbols (functions, classes, imports) from files using AST

## Setup

### 1. Install Dependencies

First, ensure the MCP package is installed:

```bash
cd backend
pip install -r requirements.txt
# or if using pyproject.toml
pip install -e .
```

### 2. Integration with Claude Agent SDK (Automatic)

**Important:** The MCP server is **automatically launched** by the Claude Agent SDK when needed. You do NOT need to start it manually.

The MCP server is configured in the `agent_chat.py` file when creating `ClaudeAgentOptions`. When the SDK needs to use MCP tools, it automatically spawns the MCP server as a subprocess. The configuration includes:

```python
agent_options = ClaudeAgentOptions(
    # ... other options ...
    mcp_servers={
        "agent-tools": {
            "command": "python",
            "args": [str(Path(__file__).parent.parent.parent.parent / "run_mcp_server.py")],
            "env": {
                "repo_path": repo_path,
                "branch": task.agent_branch_name,
                "workspace_id": str(workspace_id),
                "task_id": str(task_id),
            }
        }
    }
)
```

## Context Variables

The MCP server relies on environment variables for context:

- **repo_path**: Path to the repository being worked on
- **branch**: Git branch name
- **workspace_id**: Workspace identifier
- **task_id**: Task identifier

These are automatically set when the MCP server is launched by the Claude Agent SDK as a subprocess.

## How It Works (Automatic Launch)

1. You configure `mcp_servers` in `ClaudeAgentOptions` (already done in `agent_chat.py`)
2. When a task starts, the SDK sees the MCP configuration
3. **SDK automatically launches** `python run_mcp_server.py` as a subprocess
4. MCP server communicates with SDK via stdio using MCP protocol
5. When Claude needs a tool (e.g., "search_code"), SDK sends MCP request
6. MCP server executes the tool and returns results
7. When the task completes, **SDK automatically terminates** the MCP server subprocess

**You never need to manually start or stop the MCP server - it's all managed by the SDK!**

## Architecture

```
ClaudeAgentOptions
    |
    +-- mcp_servers config
            |
            +-- Launches: python run_mcp_server.py
                    |
                    +-- AgentToolMCPServer
                            |
                            +-- AgentToolManager
                                    |
                                    +-- AgentToolRegistry
                                            |
                                            +-- Individual Tools
                                                (SearchCodeTool, RunTestsTool, etc.)
```

## Tool Execution Flow

1. Claude Agent SDK needs to use a tool (e.g., "search_code")
2. SDK sends MCP `tools/call` request to MCP server
3. MCP server receives request and extracts tool name and arguments
4. MCP server calls `tool_manager.execute_tool()` with proper context
5. Tool executes and returns `ToolResult`
6. MCP server converts result to MCP `TextContent` format
7. Result is sent back to Claude Agent SDK
8. SDK presents result to Claude for continued reasoning

## Error Handling

The MCP server includes comprehensive error handling:

- Invalid tool names return error messages
- Tool execution exceptions are caught and returned as error responses
- Legacy tools (read_file, write_file, etc.) return special error messages indicating they must be handled separately

## Adding New Tools

To add a new tool to the MCP server:

1. Create the tool class in `backend/app/services/agent_tools/`
2. Register it in `AgentToolManager._register_all_tools()`
3. Add the tool name to the `allowed_tools` list in `agent_chat.py`
4. The tool will automatically be exposed via the MCP server

Example:

```python
# In agent_tools/my_new_tool.py
class MyNewTool(AgentTool):
    @property
    def name(self) -> str:
        return "my_new_tool"

    @property
    def description(self) -> str:
        return "Description of what this tool does"

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "param1": {
                    "type": "string",
                    "description": "Description of param1"
                }
            },
            "required": ["param1"]
        }

    def execute(self, params: dict, context: ToolContext) -> ToolResult:
        # Implementation
        pass
```

Then register it:

```python
# In agent_tool_manager.py
from .agent_tools import MyNewTool

class AgentToolManager:
    def _register_all_tools(self):
        # ... existing tools ...
        self.registry.register_class(MyNewTool)
```

And add to allowed_tools:

```python
# In agent_chat.py
allowed_tools=[
    # ... existing tools ...
    "my_new_tool",
]
```

## Testing

To test the MCP server integration:

1. Create a test task in your workspace
2. Start the agent via the API
3. Monitor the logs for MCP server startup and tool executions
4. Verify that tools are being called correctly and returning results

## Troubleshooting

### MCP Server Not Starting

- Check that `run_mcp_server.py` is executable
- Verify Python path is correct in the command
- Check logs for import errors

### Tool Execution Failures

- Verify environment variables are set correctly
- Check tool implementation for errors
- Review MCP server logs for detailed error messages

### Context Not Available

- Ensure `repo_path`, `branch`, `workspace_id`, and `task_id` are passed via environment
- Verify the ClaudeAgentOptions configuration includes these in the MCP server env

## References

- [Model Context Protocol (MCP) Documentation](https://modelcontextprotocol.io/)
- [Claude Agent SDK Documentation](https://github.com/anthropics/claude-agent-sdk)
- AgentToolManager: `backend/app/services/agent_tool_manager.py`
- MCP Server Implementation: `backend/app/services/mcp_server.py`
