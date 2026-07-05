"""Plugin registry — manifest-driven, loaded from <repo>/plugins/*.

Plugin contract (see docs/PLUGINS.md and plugins/core for a reference):
  plugins/<name>/manifest.json   metadata, tools, permissions, settings
  plugins/<name>/handler.py      get_tools() -> dict[str, callable]

Handler signature: handler(args: dict, ctx: ToolContext) -> dict (JSON-safe).
Raise ToolError for user-facing failures.

Permission levels (enforced by executor.py, most-restrictive wins between
manifest tool-level and plugin-level):
  read_only            runs immediately
  user_confirmed_write requires user confirmation
  system_sensitive     requires confirmation; plugin disabled by default
  network_access       requires confirmation when it can spend money/leak data
  disabled             never runs
"""
from __future__ import annotations

import importlib.util
import json
import logging
import sqlite3
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

from ..config import REPO_ROOT

log = logging.getLogger("athena.plugins")

PERMISSION_LEVELS = [
    "read_only", "user_confirmed_write", "system_sensitive", "network_access", "disabled",
]
# Levels that require an explicit user confirmation before execution
CONFIRM_LEVELS = {"user_confirmed_write", "system_sensitive", "network_access"}


class ToolError(Exception):
    """User-facing tool failure (message is safe to show in the UI)."""


@dataclass
class ToolContext:
    """Handed to every tool handler."""
    conn: sqlite3.Connection
    plugin_settings: dict[str, Any]
    workspace_id: str | None = None


@dataclass
class ToolDef:
    name: str
    description: str
    permission: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    handler: Callable[[dict[str, Any], ToolContext], dict[str, Any]] | None = None


@dataclass
class Plugin:
    name: str
    display_name: str
    description: str
    version: str
    permission: str
    default_enabled: bool
    placeholder: bool                    # true = architecture stub, no real handlers yet
    settings: dict[str, Any] = field(default_factory=dict)
    tools: dict[str, ToolDef] = field(default_factory=dict)
    load_error: str = ""


class PluginRegistry:
    def __init__(self, plugins_dir: Path | None = None) -> None:
        self.plugins_dir = plugins_dir or (REPO_ROOT / "plugins")
        self.plugins: dict[str, Plugin] = {}
        self.reload()

    def reload(self) -> None:
        self.plugins.clear()
        if not self.plugins_dir.exists():
            log.warning("Plugins dir missing: %s", self.plugins_dir)
            return
        for manifest_path in sorted(self.plugins_dir.glob("*/manifest.json")):
            try:
                self._load(manifest_path)
            except Exception as exc:  # noqa: BLE001 — one bad plugin must not kill the app
                name = manifest_path.parent.name
                log.error("Failed to load plugin %s: %s", name, exc)
                self.plugins[name] = Plugin(
                    name=name, display_name=name, description="", version="0",
                    permission="disabled", default_enabled=False,
                    placeholder=True, load_error=str(exc),
                )

    def _load(self, manifest_path: Path) -> None:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        name = manifest["name"]
        plugin = Plugin(
            name=name,
            display_name=manifest.get("display_name", name),
            description=manifest.get("description", ""),
            version=manifest.get("version", "0.1.0"),
            permission=manifest.get("permission", "read_only"),
            default_enabled=manifest.get("enabled", True),
            placeholder=manifest.get("placeholder", False),
            settings=manifest.get("settings", {}),
        )
        handlers: dict[str, Callable] = {}
        handler_file = manifest_path.parent / "handler.py"
        if handler_file.exists() and not plugin.placeholder:
            spec = importlib.util.spec_from_file_location(f"athena_plugin_{name}", handler_file)
            module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
            spec.loader.exec_module(module)  # type: ignore[union-attr]
            handlers = module.get_tools()

        for t in manifest.get("tools", []):
            plugin.tools[t["name"]] = ToolDef(
                name=t["name"],
                description=t.get("description", ""),
                permission=t.get("permission", plugin.permission),
                input_schema=t.get("input_schema", {}),
                output_schema=t.get("output_schema", {}),
                handler=handlers.get(t["name"]),
            )
        self.plugins[name] = plugin

    # ---- state helpers (enabled flag + settings live in DB) ----

    def is_enabled(self, conn: sqlite3.Connection, name: str) -> bool:
        plugin = self.plugins.get(name)
        if plugin is None:
            return False
        row = conn.execute("SELECT enabled FROM plugin_state WHERE name=?", (name,)).fetchone()
        return bool(row["enabled"]) if row else plugin.default_enabled

    def set_enabled(self, conn: sqlite3.Connection, name: str, enabled: bool) -> None:
        conn.execute(
            "INSERT INTO plugin_state(name,enabled) VALUES(?,?) "
            "ON CONFLICT(name) DO UPDATE SET enabled=excluded.enabled",
            (name, int(enabled)),
        )

    def effective_settings(self, conn: sqlite3.Connection, name: str) -> dict[str, Any]:
        plugin = self.plugins.get(name)
        base = dict(plugin.settings) if plugin else {}
        row = conn.execute("SELECT settings FROM plugin_state WHERE name=?", (name,)).fetchone()
        if row and row["settings"]:
            base.update(json.loads(row["settings"]))
        return base


@lru_cache
def get_plugin_registry() -> PluginRegistry:
    return PluginRegistry()
