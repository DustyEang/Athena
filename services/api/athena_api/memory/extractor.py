"""Memory extraction — after a chat exchange, a LOCAL model quietly looks
for durable facts worth remembering. Never uses premium tokens.

Behavior by memory_mode:
  off            skipped entirely
  ask            facts saved as pending proposals → user approves in Memory UI
  auto_important saved directly, but only importance >= 0.7
  project_only   saved directly, only when a workspace is active (scoped)
  full           saved directly

Runs as a fire-and-forget task after the chat stream closes, on its own DB
connection. Failures are logged and ignored — extraction must never break
or slow down chat.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re

from ..config import get_settings
from ..db import db_conn, get_setting
from ..providers import ChatMessage, get_provider_registry
from .store import CATEGORIES, MemoryStore

log = logging.getLogger("athena.memory.extractor")

MAX_FACTS = 3

_PROMPT = """You extract durable facts about the user from a conversation.

Return a JSON array (possibly empty) of at most {max_facts} objects:
[{{"content": "one factual sentence about the user", "category": "<one of: {cats}>", "importance": 0.0-1.0}}]

Rules:
- Only durable facts: preferences, projects, workflows, business context, goals.
- NOT: one-off requests, the assistant's answers, temporary states, secrets/passwords.
- Write each fact so it makes sense standing alone months later.
- Return [] if nothing qualifies. Return ONLY the JSON array, no other text.

Conversation:
USER: {user}
ASSISTANT: {assistant}"""


async def extract_after_chat(
    user_message: str, assistant_reply: str, workspace_id: str | None,
) -> int:
    """Returns number of memories written (0 on any failure)."""
    try:
        return await _extract(user_message, assistant_reply, workspace_id)
    except Exception as exc:  # noqa: BLE001 — extraction is best-effort
        log.warning("Memory extraction failed: %s", exc)
        return 0


async def _extract(user_message: str, assistant_reply: str, workspace_id: str | None) -> int:
    with db_conn() as conn:
        mode = get_setting(conn, "memory_mode", "ask")
    if mode == "off":
        return 0
    if mode == "project_only" and not workspace_id:
        return 0

    registry = get_provider_registry()
    ollama = registry.get("ollama")
    status = await ollama.status()
    if not status.available:
        return 0  # local-only by design; no local model → no extraction

    settings = get_settings()
    model = (settings.ollama_default_model
             if settings.ollama_default_model in status.models or not status.models
             else status.models[0])
    prompt = _PROMPT.format(
        max_facts=MAX_FACTS, cats=", ".join(CATEGORIES),
        user=user_message[:2000], assistant=assistant_reply[:2000],
    )

    text = ""
    async for delta in ollama.stream_chat(
        [ChatMessage("user", prompt)], model, temperature=0.1, max_tokens=400,
    ):
        if delta.error:
            return 0
        text += delta.text

    facts = _parse_facts(text)
    if not facts:
        return 0

    written = 0
    with db_conn() as conn:
        store = MemoryStore(conn)
        for fact in facts[:MAX_FACTS]:
            importance = float(fact.get("importance", 0.5))
            if mode == "auto_important" and importance < 0.7:
                continue
            store.add(
                str(fact["content"])[:500],
                str(fact.get("category", "notes")),
                workspace_id=workspace_id,
                source="chat",
                importance=max(0.0, min(1.0, importance)),
                confidence=0.6,             # model-extracted < user-stated
                pending=(mode == "ask"),
            )
            written += 1
    if written:
        log.info("Memory extraction: %d fact(s) written (mode=%s)", written, mode)
    return written


def _parse_facts(text: str) -> list[dict]:
    """Pull the first JSON array out of model output (tolerates chatter)."""
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return []
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    return [f for f in data if isinstance(f, dict) and f.get("content")]


def schedule_extraction(user_message: str, assistant_reply: str,
                        workspace_id: str | None) -> None:
    """Fire-and-forget from the chat endpoint (needs a running event loop)."""
    asyncio.get_event_loop().create_task(
        extract_after_chat(user_message, assistant_reply, workspace_id)
    )
