#!/usr/bin/env python
"""Launcher script for the Agent Tools MCP server."""

import sys
import asyncio
from pathlib import Path

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app.services.mcp_server import main

if __name__ == "__main__":
    asyncio.run(main())
