"""Fable 5 provider — premium model via the Anthropic Messages API.

Only active when ATHENA_FABLE5_API_KEY is set. The router treats this as
the expensive tier: hard planning, large-architecture, complex debugging.
Cost guardrails (ask-before-premium, budget limit) are enforced by the
router *before* this provider is ever called.

TODO(cursor): switch to true SSE streaming (`"stream": true` + event
parsing). v1 does a single non-streaming request and emits it as one delta,
which keeps the code simple and still works with the chat UI.
"""
from __future__ import annotations

import logging
from typing import AsyncIterator

import httpx

from ..config import get_settings
from .base import (
    AgentTurn, ChatMessage, ModelProvider, ProviderStatus, StreamDelta,
    ToolCallRequest, ToolChatResponse, ToolSpec, estimate_tokens,
)

log = logging.getLogger("athena.providers.fable5")


def _turns_to_anthropic(turns: list[AgentTurn]) -> tuple[str, list[dict]]:
    """Convert agent turns to Anthropic Messages format (system, messages)."""
    system = "\n\n".join(t.content for t in turns if t.role == "system")
    messages: list[dict] = []
    for t in turns:
        if t.role == "system":
            continue
        if t.role == "assistant" and t.tool_calls:
            blocks: list[dict] = []
            if t.content:
                blocks.append({"type": "text", "text": t.content})
            blocks += [
                {"type": "tool_use", "id": c.id, "name": c.name, "input": c.args}
                for c in t.tool_calls
            ]
            messages.append({"role": "assistant", "content": blocks})
        elif t.role == "tool":
            messages.append({
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": t.tool_call_id,
                    "content": t.content,
                }],
            })
        else:
            messages.append({"role": t.role, "content": t.content})
    return system, messages


class Fable5Provider(ModelProvider):
    name = "fable5"
    kind = "premium"
    supports_tools = True

    def __init__(self) -> None:
        s = get_settings()
        self.api_key = s.fable5_api_key
        self.model = s.fable5_model
        self.api_url = s.fable5_api_url

    async def status(self) -> ProviderStatus:
        if not self.api_key:
            return ProviderStatus(
                name=self.name, available=False, kind=self.kind,
                detail="No API key configured (ATHENA_FABLE5_API_KEY). "
                       "Athena runs fine without it — premium routing is disabled.",
            )
        return ProviderStatus(
            name=self.name, available=True, kind=self.kind,
            detail="API key configured.", models=[self.model],
        )

    async def stream_chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncIterator[StreamDelta]:
        if not self.api_key:
            yield StreamDelta(done=True, error="Fable 5 provider is not configured.")
            return

        system = "\n\n".join(m.content for m in messages if m.role == "system")
        chat_msgs = [
            {"role": m.role, "content": m.content}
            for m in messages if m.role in ("user", "assistant")
        ]
        payload = {
            "model": model or self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": chat_msgs,
        }
        if system:
            payload["system"] = system

        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                resp = await client.post(
                    self.api_url,
                    json=payload,
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                text = "".join(
                    block.get("text", "")
                    for block in data.get("content", [])
                    if block.get("type") == "text"
                )
                usage = data.get("usage", {})
                yield StreamDelta(text=text)
                yield StreamDelta(
                    done=True,
                    tokens_in=usage.get("input_tokens", estimate_tokens(str(chat_msgs))),
                    tokens_out=usage.get("output_tokens", estimate_tokens(text)),
                )
        except httpx.HTTPStatusError as exc:
            log.error("Fable 5 API error %s: %s", exc.response.status_code, exc.response.text[:300])
            yield StreamDelta(done=True, error=f"Fable 5 API error {exc.response.status_code}")
        except Exception as exc:  # noqa: BLE001
            log.error("Fable 5 request failed: %s", exc)
            yield StreamDelta(done=True, error=f"Fable 5 request failed: {exc}")

    async def chat_with_tools(
        self,
        turns: list[AgentTurn],
        model: str,
        tools: list[ToolSpec],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> ToolChatResponse:
        """One agent step via Anthropic native tool use (non-streaming)."""
        if not self.api_key:
            return ToolChatResponse(error="Fable 5 provider is not configured.")
        system, messages = _turns_to_anthropic(turns)
        payload: dict = {
            "model": model or self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
            "tools": [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.input_schema or {"type": "object", "properties": {}},
                }
                for t in tools
            ],
        }
        if system:
            payload["system"] = system
        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                resp = await client.post(
                    self.api_url,
                    json=payload,
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
            text, calls = "", []
            for block in data.get("content", []):
                if block.get("type") == "text":
                    text += block.get("text", "")
                elif block.get("type") == "tool_use":
                    calls.append(ToolCallRequest(
                        id=block.get("id", ""), name=block.get("name", ""),
                        args=block.get("input", {}) or {},
                    ))
            usage = data.get("usage", {})
            return ToolChatResponse(
                text=text, tool_calls=calls,
                tokens_in=usage.get("input_tokens", 0),
                tokens_out=usage.get("output_tokens", 0),
            )
        except httpx.HTTPStatusError as exc:
            log.error("Fable 5 tool chat error %s: %s",
                      exc.response.status_code, exc.response.text[:300])
            return ToolChatResponse(error=f"Fable 5 API error {exc.response.status_code}")
        except Exception as exc:  # noqa: BLE001
            log.error("Fable 5 tool chat failed: %s", exc)
            return ToolChatResponse(error=f"Fable 5 request failed: {exc}")
