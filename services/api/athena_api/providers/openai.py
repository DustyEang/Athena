"""OpenAI provider — premium models via the Chat Completions API.

Only active when ATHENA_OPENAI_API_KEY is set. Fills the same premium
tier as Fable 5; the router prefers Fable 5 when both are configured.
Cost guardrails (ask-before-premium, budget limit) are enforced by the
router before this provider is called.

GPT-5-family quirks handled here: those models take `max_completion_tokens`
(not `max_tokens`) and reject non-default `temperature`, so both are set
per model family.
"""
from __future__ import annotations

import json
import logging
from typing import AsyncIterator

import httpx

from ..config import get_settings
from .base import (
    AgentTurn, ChatMessage, ModelProvider, ProviderStatus, StreamDelta,
    ToolCallRequest, ToolChatResponse, ToolSpec, estimate_tokens,
)

log = logging.getLogger("athena.providers.openai")


def _token_params(model: str, max_tokens: int, temperature: float) -> dict:
    """GPT-5 family: max_completion_tokens, fixed temperature."""
    if model.startswith("gpt-5"):
        return {"max_completion_tokens": max_tokens}
    return {"max_tokens": max_tokens, "temperature": temperature}


def _turns_to_openai(turns: list[AgentTurn]) -> list[dict]:
    """Convert agent turns to OpenAI chat format."""
    messages: list[dict] = []
    for t in turns:
        if t.role == "assistant" and t.tool_calls:
            messages.append({
                "role": "assistant",
                "content": t.content or None,
                "tool_calls": [
                    {
                        "id": c.id,
                        "type": "function",
                        "function": {"name": c.name, "arguments": json.dumps(c.args)},
                    }
                    for c in t.tool_calls
                ],
            })
        elif t.role == "tool":
            messages.append({
                "role": "tool",
                "tool_call_id": t.tool_call_id,
                "content": t.content,
            })
        else:
            messages.append({"role": t.role, "content": t.content})
    return messages


class OpenAIProvider(ModelProvider):
    name = "openai"
    kind = "premium"
    supports_tools = True

    def __init__(self) -> None:
        s = get_settings()
        self.api_key = s.openai_api_key
        self.model = s.openai_model
        self.api_url = s.openai_api_url

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def status(self) -> ProviderStatus:
        if not self.api_key:
            return ProviderStatus(
                name=self.name, available=False, kind=self.kind,
                detail="No API key configured (ATHENA_OPENAI_API_KEY). "
                       "Athena runs fine without it.",
            )
        models = [self.model] + [m for m in get_settings().openai_extra_models if m != self.model]
        return ProviderStatus(
            name=self.name, available=True, kind=self.kind,
            detail="API key configured.", models=models,
        )

    async def stream_chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncIterator[StreamDelta]:
        if not self.api_key:
            yield StreamDelta(done=True, error="OpenAI provider is not configured.")
            return

        use_model = model or self.model
        payload = {
            "model": use_model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
            "stream_options": {"include_usage": True},
            **_token_params(use_model, max_tokens, temperature),
        }
        tokens_in = tokens_out = 0
        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                async with client.stream(
                    "POST", self.api_url, json=payload, headers=self._headers(),
                ) as resp:
                    if resp.status_code != 200:
                        body = (await resp.aread()).decode("utf-8", "replace")[:300]
                        log.error("OpenAI API error %s: %s", resp.status_code, body)
                        yield StreamDelta(done=True, error=f"OpenAI API error {resp.status_code}")
                        return
                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue
                        usage = chunk.get("usage")
                        if usage:
                            tokens_in = usage.get("prompt_tokens", 0)
                            tokens_out = usage.get("completion_tokens", 0)
                        choices = chunk.get("choices") or []
                        if choices:
                            text = (choices[0].get("delta") or {}).get("content") or ""
                            if text:
                                yield StreamDelta(text=text)
            yield StreamDelta(
                done=True,
                tokens_in=tokens_in or estimate_tokens(str(payload["messages"])),
                tokens_out=tokens_out,
            )
        except Exception as exc:  # noqa: BLE001
            log.error("OpenAI request failed: %s", exc)
            yield StreamDelta(done=True, error=f"OpenAI request failed: {exc}")

    async def chat_with_tools(
        self,
        turns: list[AgentTurn],
        model: str,
        tools: list[ToolSpec],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> ToolChatResponse:
        """One agent step via OpenAI native function calling (non-streaming)."""
        if not self.api_key:
            return ToolChatResponse(error="OpenAI provider is not configured.")
        use_model = model or self.model
        payload: dict = {
            "model": use_model,
            "messages": _turns_to_openai(turns),
            **_token_params(use_model, max_tokens, temperature),
        }
        if tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.input_schema or {"type": "object", "properties": {}},
                    },
                }
                for t in tools
            ]
        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                resp = await client.post(self.api_url, json=payload, headers=self._headers())
                resp.raise_for_status()
                data = resp.json()
            msg = (data.get("choices") or [{}])[0].get("message") or {}
            calls = []
            for c in msg.get("tool_calls") or []:
                fn = c.get("function") or {}
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                calls.append(ToolCallRequest(
                    id=c.get("id", ""), name=fn.get("name", ""), args=args,
                ))
            usage = data.get("usage", {})
            return ToolChatResponse(
                text=msg.get("content") or "",
                tool_calls=calls,
                tokens_in=usage.get("prompt_tokens", 0),
                tokens_out=usage.get("completion_tokens", 0),
            )
        except httpx.HTTPStatusError as exc:
            log.error("OpenAI tool chat error %s: %s",
                      exc.response.status_code, exc.response.text[:300])
            return ToolChatResponse(error=f"OpenAI API error {exc.response.status_code}")
        except Exception as exc:  # noqa: BLE001
            log.error("OpenAI tool chat failed: %s", exc)
            return ToolChatResponse(error=f"OpenAI request failed: {exc}")
