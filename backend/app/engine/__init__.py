"""Avery Engine - Core plugin system and extensibility hooks."""

from app.engine.plugins import AveryPlugin, get_plugin, load_plugin

__all__ = ["AveryPlugin", "get_plugin", "load_plugin"]
