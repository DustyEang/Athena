"""Chat endpoint — routing, memory recall, agent tool loop, SSE streaming,
usage tracking, post-chat memory extraction.

SSE event shapes (one JSON object per `data:` line):
  {"type":"routing", ...RoutingDecision}    first event, always
  {"type":"premium_confirmation_required"}  stream ends; UI asks the user,
                                            then re-sends with confirm_premium=true
  {"type":"delta","text":"..."}             streamed model text
  {"type":"tool_call","plugin","tool","args","call_id"}     agent loop
  {"type":"tool_result","call_id","status","preview"}       agent loop
  {"type":"done","usage":{...}}             final event
  {"type":"error","message":"..."}          terminal failure
"""
from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import time
from typing import AsyncIterator

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..db import db_conn, get_db, get_setting, new_id, rows_to_dicts
from ..memory import MemoryStore
from ..memory.extractor import extract_after_chat
from ..providers import ChatMessage, get_provider_registry
from ..providers.base import AgentTurn
from ..agent import collect_tool_specs, run_agent
from ..routing import route_request
from ..routing.costs import record_usage

log = logging.getLogger("athena.chat")
router = APIRouter(tags=["chat"])

SYSTEM_PROMPT = (
    "You are Athena, a local-first personal AI chief of staff for a hands-on "
    "entrepreneur and builder. Be direct, practical, and concise. You help with "
    "software projects, business operations, documents, and automation. "
    "You have tools — use them when they genuinely help (searching granted "
    "folders, reading files, saving notes, checking git). Some tools require "
    "the user's approval; when a tool reports it is awaiting approval, tell "
    "the user and stop — never pretend an unapproved action happened."
)
MAX_HISTORY_MESSAGES = 12  # context trimming: recent turns only, summarize later


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    conversation_id: str | None = None
    workspace_id: str | None = None
    model_override: str | None = None   # "provider:model"
    confirm_premium: bool = False


@router.post("/chat")
async def chat_endpoint(req: ChatRequest, request: Request, conn: sqlite3.Connection = Depends(get_db)):
    request_id = getattr(request.state, "request_id", new_id())

    # Conversation bookkeeping
    conversation_id = req.conversation_id
    if conversation_id is None:
        conversation_id = new_id()
        conn.execute(
            "INSERT INTO conversations(id,workspace_id,title,created_at) VALUES(?,?,?,?)",
            (conversation_id, req.workspace_id, req.message[:60], time.time()),
        )
    conn.execute(
        "INSERT INTO messages(id,conversation_id,role,content,request_id,created_at) "
        "VALUES(?,?,?,?,?,?)",
        (new_id(), conversation_id, "user", req.message, request_id, time.time()),
    )

    decision = await route_request(
        conn, req.message,
        model_override=req.model_override, confirm_premium=req.confirm_premium,
    )

    # Build the prompt: system + summarized memory recall + trimmed history
    turns: list[AgentTurn] = [AgentTurn(role="system", content=SYSTEM_PROMPT)]
    if get_setting(conn, "memory_mode", "ask") != "off":
        recall = MemoryStore(conn).recall_block(req.message)
        if recall:
            turns.append(AgentTurn(role="system", content=recall))
    history = conn.execute(
        "SELECT role, content FROM messages WHERE conversation_id=? "
        "AND role IN ('user','assistant') ORDER BY created_at DESC LIMIT ?",
        (conversation_id, MAX_HISTORY_MESSAGES),
    ).fetchall()
    for row in reversed(rows_to_dicts(history)):
        turns.append(AgentTurn(role=row["role"], content=row["content"]))

    provider = get_provider_registry().get(decision.provider)
    use_agent = (
        bool(get_setting(conn, "agent_tools_enabled", True))
        and provider is not None
        and provider.supports_tools
        and not decision.needs_premium_confirmation
        and bool(collect_tool_specs(conn))
    )

    conn.commit()  # persist user message before the long-lived stream starts

    async def event_stream() -> AsyncIterator[str]:
        def sse(obj: dict) -> str:
            return f"data: {json.dumps(obj)}\n\n"

        yield sse({
            "type": "routing", "provider": decision.provider, "model": decision.model,
            "tier": decision.tier, "task_type": decision.task_type,
            "reason": decision.reason, "warnings": decision.warnings,
            "conversation_id": conversation_id, "request_id": request_id,
            "agent_mode": use_agent,
        })
        if decision.needs_premium_confirmation:
            yield sse({"type": "premium_confirmation_required",
                       "provider": decision.provider, "model": decision.model})
            return

        full_text, tokens_in, tokens_out, error = "", 0, 0, ""

        if use_agent:
            # Agent path: model may call tools; loop handles permissions via
            # the executor. Needs its own connection (outlives request scope).
            with db_conn() as agent_conn:
                async for event in run_agent(
                    agent_conn, turns, decision.provider, decision.model,
                    workspace_id=req.workspace_id,
                ):
                    if event["type"] == "delta":
                        full_text += event["text"]
                        yield sse(event)
                    elif event["type"] in ("tool_call", "tool_result"):
                        yield sse(event)
                    elif event["type"] == "error":
                        error = event["message"]
                        yield sse(event)
                    elif event["type"] == "done":
                        tokens_in = event["tokens_in"]
                        tokens_out = event["tokens_out"]
        else:
            messages = [ChatMessage(t.role, t.content) for t in turns]
            async for delta in provider.stream_chat(messages, decision.model):
                if delta.error:
                    error = delta.error
                    yield sse({"type": "error", "message": delta.error})
                    break
                if delta.text:
                    full_text += delta.text
                    yield sse({"type": "delta", "text": delta.text})
                if delta.done:
                    tokens_in, tokens_out = delta.tokens_in, delta.tokens_out

        # Streams outlive the request-scoped conn — use a fresh one to persist.
        with db_conn() as wconn:
            if full_text and not error:
                wconn.execute(
                    "INSERT INTO messages(id,conversation_id,role,content,provider,"
                    "model,request_id,created_at) VALUES(?,?,?,?,?,?,?,?)",
                    (new_id(), conversation_id, "assistant", full_text,
                     decision.provider, decision.model, request_id, time.time()),
                )
            cost = record_usage(
                wconn, request_id=request_id, provider=decision.provider,
                model=decision.model, task_type=decision.task_type,
                tokens_in=tokens_in, tokens_out=tokens_out,
                routing_reason=decision.reason,
            )
        if not error:
            yield sse({"type": "done", "usage": {
                "tokens_in": tokens_in, "tokens_out": tokens_out,
                "est_cost_usd": round(cost, 6),
                "provider": decision.provider, "model": decision.model,
            }})
            # Quietly look for durable facts (local model only; respects
            # memory_mode). Fire-and-forget: never blocks the response.
            if full_text:
                asyncio.create_task(extract_after_chat(
                    req.message, full_text, req.workspace_id,
                ))

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/chat/conversations")
def list_conversations(workspace_id: str | None = None, conn: sqlite3.Connection = Depends(get_db)):
    q = "SELECT * FROM conversations"
    params: list = []
    if workspace_id:
        q += " WHERE workspace_id=?"
        params.append(workspace_id)
    q += " ORDER BY created_at DESC LIMIT 100"
    return rows_to_dicts(conn.execute(q, params).fetchall())


@router.get("/chat/conversations/{conversation_id}/messages")
def get_messages(conversation_id: str, conn: sqlite3.Connection = Depends(get_db)):
    return rows_to_dicts(conn.execute(
        "SELECT * FROM messages WHERE conversation_id=? ORDER BY created_at",
        (conversation_id,),
    ).fetchall())
