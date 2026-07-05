"""Core plugin handlers. Loaded dynamically by the plugin registry —
imports from athena_api are available because the API process loads us."""
from __future__ import annotations

import subprocess
from typing import Any

from athena_api.db import get_setting
from athena_api.memory import MemoryStore
from athena_api.plugins.registry import ToolContext, ToolError


def echo(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    return {"echo": args.get("text", "")}


def add_note(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    text = (args.get("text") or "").strip()
    if not text:
        raise ToolError("Note text is required")
    mem = MemoryStore(ctx.conn).add(
        text, "notes", workspace_id=args.get("workspace_id") or ctx.workspace_id,
        source="tool",
    )
    return {"id": mem["id"], "saved": text[:80]}


def list_notes(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    notes = MemoryStore(ctx.conn).list(category="notes", limit=int(args.get("limit", 20)))
    return {"notes": [{"id": n["id"], "content": n["content"]} for n in notes]}


def launch_app(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    """Only allowlisted apps can launch — allowlist lives in settings
    (app_launcher_allowlist) so the user controls it from the UI."""
    app = (args.get("app") or "").strip().lower()
    allowlist = [a.lower() for a in get_setting(ctx.conn, "app_launcher_allowlist",
                                                ["notepad", "calc", "explorer", "mspaint"])]
    if app not in allowlist:
        raise ToolError(
            f"'{app}' is not in the app allowlist ({', '.join(allowlist)}). "
            "Add it in Settings first."
        )
    try:
        # shell=False; app name only, no arguments — keeps this launcher narrow.
        subprocess.Popen([app], shell=False)  # noqa: S603
    except OSError as exc:
        raise ToolError(f"Failed to launch '{app}': {exc}") from exc
    return {"launched": app}


def get_tools() -> dict[str, Any]:
    return {"echo": echo, "add_note": add_note, "list_notes": list_notes,
            "launch_app": launch_app}
