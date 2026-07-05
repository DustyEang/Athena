"""Agent loop — lets the model use Athena's tools mid-conversation.

Flow per user message (when the provider supports tools):
    model step ──► tool calls? ──► executor (permissions/confirmation!) ──►
    results fed back ──► model step … up to MAX_STEPS ──► final text

Safety properties (inherited, not reimplemented):
- Every call goes through plugins/executor.py — the model CANNOT bypass
  permission levels, confirmations, folder grants, or audit logging.
- Confirmation-gated tools do not block the stream: the run is created as
  pending, the model is told "awaiting user approval", and the user approves
  it in the Tool activity feed. The model explains this to the user.
- MAX_STEPS caps runaway loops; every step's tokens are accumulated.

SSE events emitted (on top of routers/chat.py's shapes):
    {"type":"tool_call","plugin","tool","args","call_id"}
    {"type":"tool_result","call_id","status","preview"}
"""
from __future__ import annotations

import json
import logging
import sqlite3
from typing import Any, AsyncIterator

from ..plugins import execute_tool, get_plugin_registry
from ..providers import get_provider_registry
from ..providers.base import AgentTurn, ToolSpec

log = logging.getLogger("athena.agent")

MAX_STEPS = 5
RESULT_CHARS_TO_MODEL = 4000   # truncate tool output fed back (context cost)
PREVIEW_CHARS = 300            # truncate preview sent to the UI


def collect_tool_specs(conn: sqlite3.Connection) -> list[ToolSpec]:
    """All tools the model may see: enabled plugin, implemented handler,
    not permission-disabled. Confirmation-gated tools ARE included — the
    executor turns them into pending confirmations, never direct runs."""
    registry = get_plugin_registry()
    specs: list[ToolSpec] = []
    for plugin in registry.plugins.values():
        if plugin.placeholder or not registry.is_enabled(conn, plugin.name):
            continue
        for tool in plugin.tools.values():
            if tool.handler is None or tool.permission == "disabled":
                continue
            desc = tool.description
            if tool.permission in ("user_confirmed_write", "system_sensitive", "network_access"):
                desc += " (Requires the user's approval before it actually runs.)"
            specs.append(ToolSpec(
                name=f"{plugin.name}__{tool.name}",
                description=desc,
                input_schema=tool.input_schema,
            ))
    return specs


async def run_agent(
    conn: sqlite3.Connection,
    turns: list[AgentTurn],
    provider_name: str,
    model: str,
    *,
    workspace_id: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Run the tool-enabled conversation. Yields SSE-ready event dicts:
    tool_call / tool_result / delta / done / error. Caller owns persistence."""
    provider = get_provider_registry().get(provider_name)
    tools = collect_tool_specs(conn)
    total_in = total_out = 0

    for step in range(MAX_STEPS):
        resp = await provider.chat_with_tools(turns, model, tools)
        total_in += resp.tokens_in
        total_out += resp.tokens_out

        if resp.error:
            yield {"type": "error", "message": resp.error}
            return

        if not resp.tool_calls:
            if resp.text:
                yield {"type": "delta", "text": resp.text}
            yield {"type": "done", "tokens_in": total_in, "tokens_out": total_out}
            return

        # Model wants tools. Surface any accompanying text, record the turn.
        if resp.text:
            yield {"type": "delta", "text": resp.text + "\n"}
        turns.append(AgentTurn(role="assistant", content=resp.text,
                               tool_calls=resp.tool_calls))

        for call in resp.tool_calls:
            plugin_name, _, tool_name = call.name.partition("__")
            yield {"type": "tool_call", "call_id": call.id,
                   "plugin": plugin_name, "tool": tool_name, "args": call.args}

            run = execute_tool(conn, plugin_name, tool_name, call.args,
                               workspace_id=workspace_id)
            conn.commit()  # confirmations/audit must be visible to the UI immediately

            if run["status"] == "pending_confirmation":
                feedback = (
                    "Status: awaiting user approval. This action needs explicit "
                    "confirmation; the user must approve it in the Tool activity "
                    "panel. Tell the user what you asked to do and that it is "
                    "waiting for their approval — do not retry it."
                )
                preview = "awaiting user approval"
            elif run["status"] == "ok":
                result_json = json.dumps(run.get("result"), default=str)
                feedback = result_json[:RESULT_CHARS_TO_MODEL]
                preview = result_json[:PREVIEW_CHARS]
            else:  # error / denied
                feedback = f"Tool failed: {run.get('error', run['status'])}"
                preview = str(run.get("error", run["status"]))[:PREVIEW_CHARS]

            yield {"type": "tool_result", "call_id": call.id,
                   "status": run["status"], "preview": preview}
            turns.append(AgentTurn(role="tool", content=feedback,
                                   tool_call_id=call.id))

    log.warning("Agent hit MAX_STEPS (%d) — forcing a final answer", MAX_STEPS)
    yield {"type": "delta",
           "text": "(I reached my tool-use limit for one message — here's where "
                   "things stand based on what I ran so far.)"}
    yield {"type": "done", "tokens_in": total_in, "tokens_out": total_out}
