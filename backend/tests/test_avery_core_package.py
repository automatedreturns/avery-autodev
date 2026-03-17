"""Tests for avery_core package - the public API surface for pip consumers."""

import subprocess
import sys

import pytest

from app.engine.plugins import reset_plugin


@pytest.fixture(autouse=True)
def _reset():
    reset_plugin()
    yield
    reset_plugin()


class TestAveryCorePkgImports:
    """Verify that avery_core re-exports work correctly."""

    def test_version(self):
        from avery_core import __version__
        assert __version__ == "0.1.0"

    def test_engine_plugin_imports(self):
        from avery_core.engine.plugins import (
            AveryPlugin,
            ExecutionContext,
            ExecutionUsage,
            get_plugin,
            load_plugin,
            reset_plugin,
        )
        assert AveryPlugin is not None
        assert get_plugin() is not None

    def test_engine_init_imports(self):
        from avery_core.engine import AveryPlugin, get_plugin
        assert AveryPlugin is not None
        assert get_plugin() is not None

    def test_services_imports(self):
        from avery_core.services import (
            execute_coder_agent,
            TestGeneratorService,
            AIModelService,
        )
        assert callable(execute_coder_agent)
        assert TestGeneratorService is not None
        assert AIModelService is not None

    def test_plugin_identity(self):
        """avery_core.engine.plugins and app.engine.plugins reference the same classes."""
        from avery_core.engine.plugins import AveryPlugin as CorePlugin
        from app.engine.plugins import AveryPlugin as AppPlugin
        assert CorePlugin is AppPlugin

    def test_subclassing_from_avery_core(self):
        """Cloud repo pattern: subclass AveryPlugin from avery_core."""
        from avery_core.engine.plugins import AveryPlugin, ExecutionContext

        class CloudPlugin(AveryPlugin):
            def check_access(self, user_id, action):
                return user_id == "premium"

        plugin = CloudPlugin()
        assert plugin.check_access("premium", "agent_execute") is True
        assert plugin.check_access("free", "agent_execute") is False

        # Inherited methods still work
        ctx = ExecutionContext(action="test", user_id="u1")
        assert plugin.before_execute(ctx) is ctx
        assert plugin.get_dashboard_extras() == []


class TestAveryCLI:
    """Test CLI entry point."""

    def test_cli_version(self):
        result = subprocess.run(
            [sys.executable, "-m", "avery_core.cli", "version"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "avery-core 0.1.0" in result.stdout

    def test_cli_help(self):
        result = subprocess.run(
            [sys.executable, "-m", "avery_core.cli", "--help"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "run" in result.stdout
        assert "fix" in result.stdout
        assert "serve" in result.stdout
        assert "version" in result.stdout

    def test_cli_run_missing_args(self):
        result = subprocess.run(
            [sys.executable, "-m", "avery_core.cli", "run"],
            capture_output=True, text=True,
        )
        assert result.returncode != 0  # Missing required --repo and --issue

    def test_cli_no_command_shows_help(self):
        result = subprocess.run(
            [sys.executable, "-m", "avery_core.cli"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "Avery" in result.stdout
