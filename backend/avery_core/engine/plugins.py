"""Re-export plugin system for external consumers.

Usage:
    from avery_core.engine.plugins import AveryPlugin, ExecutionContext
"""

from app.engine.plugins import (  # noqa: F401
    AveryPlugin,
    ExecutionContext,
    ExecutionUsage,
    get_plugin,
    load_plugin,
    reset_plugin,
)
