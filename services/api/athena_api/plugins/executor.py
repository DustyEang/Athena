"""Tool executor — the single gate every tool call passes through.

Safety model:
- disabled plugins/tools never run
- read_only tools run immediately
- everything in CONFIRM_LEVELS creates a `pending_confirmation` tool_run;
  the UI shows it and the user approves/denies via /api/tools/confirm
- every run (and every confirmation decision) is written to tool_runs and
  audit_log — Athena never acts silently
"""
from __future__ import annotations

import json
import logging
import sqlite3
import time
from typing import Any

from ..db import audit, new_id
from .registry import CONFIRM_LEVELS, ToolContext, ToolError, get_plugin_registry

log = logging.getLogger("athena.tools")


def execute_tool(
    conn: sqlite3.Connection,
    plugin_name: str,
    tool_name: str,
    args: dict[str, Any],
    *,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Returns a tool_run record. status: ok | error | pending_confirmation."""
    registry = get_plugin_registry()
    plugin = registry.plugins.get(plugin_name)
    if plugin is None:
        return _finished_run(conn, plugin_name, tool_name, args, "error",
                             error=f"Unknown plugin '{plugin_name}'")
    if not registry.is_enabled(conn, plugin_name):
        return _finished_run(conn, plugin_name, tool_name, args, "error",
                             error=f"Plugin '{plugin_name}' is disabled")
    tool = plugin.tools.get(tool_name)
    if tool is None:
        return _finished_run(conn, plugin_name, tool_name, args, "error",
                             error=f"Unknown tool '{tool_name}' in plugin '{plugin_name}'")
    if plugin.placeholder or tool.handler is None:
        return _finished_run(conn, plugin_name, tool_name, args, "error", permission=tool.permission,
                             error=f"'{plugin.display_name}' is a placeholder — not implemented yet")
    if tool.permission == "disabled" or plugin.permission == "disabled":
        return _finished_run(conn, plugin_name, tool_name, args, "error", permission="disabled",
                             error="This tool is disabled")

    if tool.permission in CONFIRM_LEVELS:
        run_id = new_id()
        conn.execute(
            "INSERT INTO tool_runs(id,plugin,tool,args,permission,status,created_at) "
            "VALUES(?,?,?,?,?,?,?)",
            (run_id, plugin_name, tool_name, json.dumps(args), tool.permission,
             "pending_confirmation", time.time()),
        )
        audit(conn, "athena", "tool.confirmation_requested",
              f"{plugin_name}.{tool_name} args={json.dumps(args)[:300]}")
        return _get_run(conn, run_id)

    return _run_now(conn, plugin_name, tool_name, args, tool.permission, workspace_id)


def resolve_confirmation(
    conn: sqlite3.Connection, run_id: str, approved: bool,
) -> dict[str, Any]:
    row = conn.execute("SELECT * FROM tool_runs WHERE id=?", (run_id,)).fetchone()
    if row is None:
        raise ToolError(f"No tool run '{run_id}'")
    if row["status"] != "pending_confirmation":
        raise ToolError(f"Tool run '{run_id}' is not awaiting confirmation")

    if not approved:
        conn.execute(
            "UPDATE tool_runs SET status='denied', resolved_at=? WHERE id=?",
            (time.time(), run_id),
        )
        audit(conn, "user", "tool.denied", f"{row['plugin']}.{row['tool']}")
        return _get_run(conn, run_id)

    audit(conn, "user", "tool.approved", f"{row['plugin']}.{row['tool']}")
    result = _run_now(
        conn, row["plugin"], row["tool"], json.loads(row["args"]),
        row["permission"], None, existing_run_id=run_id,
    )
    return result


def _run_now(
    conn: sqlite3.Connection, plugin_name: str, tool_name: str,
    args: dict[str, Any], permission: str, workspace_id: str | None,
    existing_run_id: str | None = None,
) -> dict[str, Any]:
    registry = get_plugin_registry()
    tool = registry.plugins[plugin_name].tools[tool_name]
    ctx = ToolContext(
        conn=conn,
        plugin_settings=registry.effective_settings(conn, plugin_name),
        workspace_id=workspace_id,
    )
    run_id = existing_run_id or new_id()
    if existing_run_id is None:
        conn.execute(
            "INSERT INTO tool_runs(id,plugin,tool,args,permission,status,created_at) "
            "VALUES(?,?,?,?,?,?,?)",
            (run_id, plugin_name, tool_name, json.dumps(args), permission, "running", time.time()),
        )
    try:
        result = tool.handler(args, ctx)  # type: ignore[misc]
        conn.execute(
            "UPDATE tool_runs SET status='ok', result=?, resolved_at=? WHERE id=?",
            (json.dumps(result), time.time(), run_id),
        )
        audit(conn, f"plugin:{plugin_name}", "tool.ok", f"{tool_name}")
    except ToolError as exc:
        conn.execute(
            "UPDATE tool_runs SET status='error', error=?, resolved_at=? WHERE id=?",
            (str(exc), time.time(), run_id),
        )
        audit(conn, f"plugin:{plugin_name}", "tool.error", f"{tool_name}: {exc}")
    except Exception as exc:  # noqa: BLE001 — surface, never hide
        log.exception("Tool %s.%s crashed", plugin_name, tool_name)
        conn.execute(
            "UPDATE tool_runs SET status='error', error=?, resolved_at=? WHERE id=?",
            (f"Internal error: {exc}", time.time(), run_id),
        )
        audit(conn, f"plugin:{plugin_name}", "tool.crash", f"{tool_name}: {exc}")
    return _get_run(conn, run_id)


def _finished_run(
    conn: sqlite3.Connection, plugin: str, tool: str, args: dict[str, Any],
    status: str, *, error: str = "", permission: str = "unknown",
) -> dict[str, Any]:
    run_id = new_id()
    conn.execute(
        "INSERT INTO tool_runs(id,plugin,tool,args,permission,status,error,created_at,resolved_at) "
        "VALUES(?,?,?,?,?,?,?,?,?)",
        (run_id, plugin, tool, json.dumps(args), permission, status, error,
         time.time(), time.time()),
    )
    return _get_run(conn, run_id)


def _get_run(conn: sqlite3.Connection, run_id: str) -> dict[str, Any]:
    row = dict(conn.execute("SELECT * FROM tool_runs WHERE id=?", (run_id,)).fetchone())
    for key in ("args", "result"):
        if row.get(key):
            try:
                row[key] = json.loads(row[key])
            except (TypeError, json.JSONDecodeError):
                pass
    return row
