"""
Avery Plugin System

Defines the AveryPlugin base class with hooks that Cloud (or custom plugins) can override.
Community Edition ships with the default AveryPlugin which reads API keys from env
and imposes no access restrictions.

Usage:
    from app.engine.plugins import get_plugin

    plugin = get_plugin()
    api_key = plugin.resolve_api_key("anthropic")
    if plugin.check_access(user_id, "agent_execute"):
        ctx = plugin.before_execute("agent_execute", {"user_id": user_id, ...})
        result = run_agent(ctx)
        plugin.after_execute("agent_execute", result, usage)
"""

import importlib
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ExecutionContext:
    """Context passed through the plugin lifecycle for a single action."""

    action: str
    user_id: str
    workspace_id: Optional[str] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class ExecutionUsage:
    """Token/cost usage from a completed action."""

    provider: str = ""
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    metadata: dict = field(default_factory=dict)


class AveryPlugin:
    """
    Base plugin class for Avery Community Edition.

    All methods have sensible CE defaults. Cloud or custom plugins
    override specific methods to add billing, managed keys, analytics, etc.
    """

    def resolve_api_key(self, provider: str) -> Optional[str]:
        """
        Resolve an API key for the given AI provider.

        CE default: reads from environment variables.
        Cloud override: picks from a managed, rotating key pool.

        Args:
            provider: One of "anthropic", "openai", "azure_openai", "gemini"

        Returns:
            The API key string, or None if not configured.
        """
        env_map = {
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "azure_openai": "AZURE_OPENAI_API_KEY",
            "gemini": "GEMINI_API_KEY",
        }
        env_var = env_map.get(provider)
        if not env_var:
            logger.warning(f"Unknown AI provider: {provider}")
            return None
        return os.getenv(env_var)

    def check_access(self, user_id: str, action: str) -> bool:
        """
        Check whether a user is allowed to perform an action.

        CE default: always True (no restrictions).
        Cloud override: checks credit balance against estimated cost.

        Args:
            user_id: The user requesting the action.
            action: The action type (e.g., "agent_execute", "test_generate", "ci_fix").

        Returns:
            True if the user may proceed, False otherwise.
        """
        return True

    def before_execute(self, context: ExecutionContext) -> ExecutionContext:
        """
        Called before an action is executed.

        CE default: passes context through unchanged.
        Cloud override: estimates credit cost, reserves credits, attaches hold ID.

        Args:
            context: The execution context for this action.

        Returns:
            The (possibly enriched) execution context.
        """
        return context

    def after_execute(
        self,
        context: ExecutionContext,
        result: dict[str, Any],
        usage: ExecutionUsage,
    ) -> None:
        """
        Called after an action completes (success or failure).

        CE default: no-op.
        Cloud override: calculates actual credit cost, settles the hold,
        records the transaction in the credit ledger.

        Args:
            context: The execution context (same object returned by before_execute).
            result: The action result dict (must include "success": bool).
            usage: Token/cost usage from the AI provider.
        """
        pass

    def on_execute_error(
        self,
        context: ExecutionContext,
        error: Exception,
    ) -> None:
        """
        Called when an action fails with an exception.

        CE default: no-op.
        Cloud override: releases the credit hold, optionally refunds.

        Args:
            context: The execution context.
            error: The exception that was raised.
        """
        pass

    def get_dashboard_extras(self) -> list[dict[str, Any]]:
        """
        Return extra dashboard widgets/sections for the frontend.

        CE default: empty list.
        Cloud override: credit balance card, usage charts, billing link, etc.

        Returns:
            List of widget descriptors:
            [{"type": "credit_balance", "data": {...}}, ...]
        """
        return []


# ---------------------------------------------------------------------------
# Plugin registry
# ---------------------------------------------------------------------------

_plugin_instance: Optional[AveryPlugin] = None


def load_plugin(plugin_class_path: Optional[str] = None) -> AveryPlugin:
    """
    Load and instantiate the configured plugin.

    Resolution order:
    1. Explicit `plugin_class_path` argument
    2. AVERY_PLUGIN_CLASS environment variable
    3. Default AveryPlugin (CE)

    Args:
        plugin_class_path: Dotted path to the plugin class,
            e.g. "cloud.plugin.AveryCloudPlugin"

    Returns:
        An instantiated AveryPlugin (or subclass).
    """
    global _plugin_instance

    class_path = plugin_class_path or os.getenv("AVERY_PLUGIN_CLASS")

    if class_path:
        try:
            module_path, class_name = class_path.rsplit(".", 1)
            module = importlib.import_module(module_path)
            plugin_cls = getattr(module, class_name)
            if not issubclass(plugin_cls, AveryPlugin):
                raise TypeError(
                    f"{class_path} is not a subclass of AveryPlugin"
                )
            _plugin_instance = plugin_cls()
            logger.info(f"Loaded plugin: {class_path}")
        except Exception:
            logger.exception(f"Failed to load plugin '{class_path}', falling back to CE default")
            _plugin_instance = AveryPlugin()
    else:
        _plugin_instance = AveryPlugin()
        logger.info("Using default AveryPlugin (Community Edition)")

    return _plugin_instance


def get_plugin() -> AveryPlugin:
    """
    Get the current plugin instance. Loads the default if not yet initialized.

    Returns:
        The active AveryPlugin instance.
    """
    global _plugin_instance
    if _plugin_instance is None:
        load_plugin()
    return _plugin_instance


def reset_plugin() -> None:
    """Reset the plugin instance. Useful for testing."""
    global _plugin_instance
    _plugin_instance = None
