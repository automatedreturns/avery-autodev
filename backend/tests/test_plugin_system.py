"""Tests for the Avery plugin system."""

import os
from unittest.mock import patch

import pytest

from app.engine.plugins import (
    AveryPlugin,
    ExecutionContext,
    ExecutionUsage,
    get_plugin,
    load_plugin,
    reset_plugin,
)


@pytest.fixture(autouse=True)
def _reset():
    """Reset plugin state between tests."""
    reset_plugin()
    yield
    reset_plugin()


class TestAveryPluginDefaults:
    """Test CE default behavior of AveryPlugin."""

    def test_resolve_api_key_from_env(self):
        plugin = AveryPlugin()
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test-123"}):
            assert plugin.resolve_api_key("anthropic") == "sk-test-123"

    def test_resolve_api_key_missing(self):
        plugin = AveryPlugin()
        with patch.dict(os.environ, {}, clear=True):
            # Remove key if it exists
            os.environ.pop("ANTHROPIC_API_KEY", None)
            assert plugin.resolve_api_key("anthropic") is None

    def test_resolve_api_key_unknown_provider(self):
        plugin = AveryPlugin()
        assert plugin.resolve_api_key("unknown_provider") is None

    def test_resolve_api_key_all_providers(self):
        plugin = AveryPlugin()
        env = {
            "ANTHROPIC_API_KEY": "key-a",
            "OPENAI_API_KEY": "key-o",
            "AZURE_OPENAI_API_KEY": "key-az",
            "GEMINI_API_KEY": "key-g",
        }
        with patch.dict(os.environ, env):
            assert plugin.resolve_api_key("anthropic") == "key-a"
            assert plugin.resolve_api_key("openai") == "key-o"
            assert plugin.resolve_api_key("azure_openai") == "key-az"
            assert plugin.resolve_api_key("gemini") == "key-g"

    def test_check_access_always_true(self):
        plugin = AveryPlugin()
        assert plugin.check_access("user-1", "agent_execute") is True
        assert plugin.check_access("user-2", "test_generate") is True
        assert plugin.check_access("user-3", "ci_fix") is True

    def test_before_execute_passthrough(self):
        plugin = AveryPlugin()
        ctx = ExecutionContext(action="agent_execute", user_id="user-1")
        result = plugin.before_execute(ctx)
        assert result is ctx

    def test_after_execute_noop(self):
        plugin = AveryPlugin()
        ctx = ExecutionContext(action="agent_execute", user_id="user-1")
        usage = ExecutionUsage(provider="anthropic", input_tokens=100)
        # Should not raise
        plugin.after_execute(ctx, {"success": True}, usage)

    def test_on_execute_error_noop(self):
        plugin = AveryPlugin()
        ctx = ExecutionContext(action="agent_execute", user_id="user-1")
        plugin.on_execute_error(ctx, RuntimeError("test"))

    def test_get_dashboard_extras_empty(self):
        plugin = AveryPlugin()
        assert plugin.get_dashboard_extras() == []


class TestPluginRegistry:
    """Test plugin loading and registry."""

    def test_load_default_plugin(self):
        plugin = load_plugin()
        assert isinstance(plugin, AveryPlugin)
        assert type(plugin) is AveryPlugin

    def test_get_plugin_lazy_loads(self):
        plugin = get_plugin()
        assert isinstance(plugin, AveryPlugin)

    def test_get_plugin_returns_same_instance(self):
        p1 = get_plugin()
        p2 = get_plugin()
        assert p1 is p2

    def test_load_plugin_from_env(self):
        with patch.dict(os.environ, {
            "AVERY_PLUGIN_CLASS": "tests.test_plugin_system.MockPlugin"
        }):
            plugin = load_plugin()
            assert isinstance(plugin, MockPlugin)

    def test_load_plugin_explicit_path(self):
        plugin = load_plugin("tests.test_plugin_system.MockPlugin")
        assert isinstance(plugin, MockPlugin)

    def test_load_plugin_invalid_path_falls_back(self):
        plugin = load_plugin("nonexistent.module.BadPlugin")
        assert type(plugin) is AveryPlugin

    def test_load_plugin_not_subclass_falls_back(self):
        plugin = load_plugin("tests.test_plugin_system.NotAPlugin")
        assert type(plugin) is AveryPlugin

    def test_reset_plugin(self):
        p1 = get_plugin()
        reset_plugin()
        p2 = get_plugin()
        assert p1 is not p2


class TestCustomPlugin:
    """Test that custom plugins can override behavior."""

    def test_custom_resolve_api_key(self):
        plugin = MockPlugin()
        assert plugin.resolve_api_key("anthropic") == "mock-key-anthropic"

    def test_custom_check_access(self):
        plugin = MockPlugin()
        assert plugin.check_access("allowed-user", "agent_execute") is True
        assert plugin.check_access("blocked-user", "agent_execute") is False

    def test_custom_before_execute(self):
        plugin = MockPlugin()
        ctx = ExecutionContext(action="agent_execute", user_id="user-1")
        result = plugin.before_execute(ctx)
        assert result.metadata.get("enriched") is True

    def test_custom_after_execute(self):
        plugin = MockPlugin()
        ctx = ExecutionContext(action="agent_execute", user_id="user-1")
        usage = ExecutionUsage(provider="anthropic", input_tokens=500)
        plugin.after_execute(ctx, {"success": True}, usage)
        assert plugin.last_usage is usage


class TestExecutionContext:
    """Test ExecutionContext dataclass."""

    def test_defaults(self):
        ctx = ExecutionContext(action="test", user_id="u1")
        assert ctx.workspace_id is None
        assert ctx.metadata == {}

    def test_full_init(self):
        ctx = ExecutionContext(
            action="agent_execute",
            user_id="u1",
            workspace_id="ws1",
            metadata={"issue_number": 42},
        )
        assert ctx.action == "agent_execute"
        assert ctx.workspace_id == "ws1"
        assert ctx.metadata["issue_number"] == 42


class TestExecutionUsage:
    """Test ExecutionUsage dataclass."""

    def test_defaults(self):
        usage = ExecutionUsage()
        assert usage.provider == ""
        assert usage.input_tokens == 0
        assert usage.output_tokens == 0

    def test_full_init(self):
        usage = ExecutionUsage(
            provider="anthropic",
            model="claude-sonnet-4-6",
            input_tokens=1000,
            output_tokens=500,
            total_tokens=1500,
        )
        assert usage.total_tokens == 1500


# -- Test fixtures (mock plugin) --


class MockPlugin(AveryPlugin):
    """A test plugin that overrides all hooks."""

    def __init__(self):
        self.last_usage = None

    def resolve_api_key(self, provider: str):
        return f"mock-key-{provider}"

    def check_access(self, user_id: str, action: str) -> bool:
        return user_id == "allowed-user"

    def before_execute(self, context: ExecutionContext) -> ExecutionContext:
        context.metadata["enriched"] = True
        return context

    def after_execute(self, context, result, usage):
        self.last_usage = usage

    def get_dashboard_extras(self):
        return [{"type": "mock_widget", "data": {}}]


class NotAPlugin:
    """Not a subclass of AveryPlugin - used to test validation."""
    pass
