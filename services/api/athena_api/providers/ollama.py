"""Ollama provider — real local model chat via the Ollama HTTP API."""
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

log = logging.getLogger("athena.providers.ollama")


def _thinking_model(model: str) -> bool:
    """Models whose 'thinking' output we suppress for clean chat replies."""
    lower = model.lower()
    return "qwen3" in lower or "deepseek-r1" in lower


def _turns_to_ollama(turns: list[AgentTurn]) -> list[dict]:
    """Convert provider-agnostic turns to Ollama's chat message format."""
    out: list[dict] = []
    for t in turns:
        if t.role == "assistant" and t.tool_calls:
            out.append({
                "role": "assistant",
                "content": t.content,
                "tool_calls": [
                    {"function": {"name": c.name, "arguments": c.args}}
                    for c in t.tool_calls
                ],
            })
        elif t.role == "tool":
            out.append({"role": "tool", "content": t.content})
        else:
            out.append({"role": t.role, "content": t.content})
    return out


class OllamaProvider(ModelProvider):
    name = "ollama"
    kind = "local"
    supports_tools = True

    def __init__(self) -> None:
        self.base_url = get_settings().ollama_url.rstrip("/")

    async def status(self) -> ProviderStatus:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                resp.raise_for_status()
                models = [m["name"] for m in resp.json().get("models", [])]
                return ProviderStatus(
                    name=self.name, available=True, kind=self.kind,
                    detail=f"Ollama reachable at {self.base_url}", models=models,
                )
        except Exception as exc:  # noqa: BLE001 — status check must never raise
            return ProviderStatus(
                name=self.name, available=False, kind=self.kind,
                detail=f"Ollama not reachable at {self.base_url} ({type(exc).__name__}). "
                       "Start it with `ollama serve`.",
            )

    async def stream_chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncIterator[StreamDelta]:
        payload = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        if _thinking_model(model):
            payload["think"] = False
        tokens_in = sum(estimate_tokens(m.content) for m in messages)
        tokens_out = 0
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                async with client.stream(
                    "POST", f"{self.base_url}/api/chat", json=payload
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line.strip():
                            continue
                        data = json.loads(line)
                        chunk = data.get("message", {}).get("content", "")
                        if chunk:
                            tokens_out += estimate_tokens(chunk)
                            yield StreamDelta(text=chunk)
                        if data.get("done"):
                            # Ollama reports real counts when done
                            yield StreamDelta(
                                done=True,
                                tokens_in=data.get("prompt_eval_count", tokens_in),
                                tokens_out=data.get("eval_count", tokens_out),
                            )
                            return
            yield StreamDelta(done=True, tokens_in=tokens_in, tokens_out=tokens_out)
        except Exception as exc:  # noqa: BLE001
            log.error("Ollama stream failed: %s", exc)
            yield StreamDelta(done=True, error=f"Ollama error: {exc}")

    async def chat_with_tools(
        self,
        turns: list[AgentTurn],
        model: str,
        tools: list[ToolSpec],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> ToolChatResponse:
        """One agent step via Ollama's native tool calling (non-streaming).
        Note: small models vary in tool-call reliability — llama3.1/3.2 and
        qwen2.5 families work; the agent loop tolerates plain-text answers."""
        payload = {
            "model": model,
            "messages": _turns_to_ollama(turns),
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.input_schema or {"type": "object", "properties": {}},
                    },
                }
                for t in tools
            ],
        }
        if _thinking_model(model):
            payload["think"] = False
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                resp = await client.post(f"{self.base_url}/api/chat", json=payload)
                resp.raise_for_status()
                data = resp.json()
            msg = data.get("message", {})
            calls = []
            for i, c in enumerate(msg.get("tool_calls") or []):
                fn = c.get("function", {})
                args = fn.get("arguments") or {}
                if isinstance(args, str):  # some models return JSON strings
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                calls.append(ToolCallRequest(id=f"ollama-{i}", name=fn.get("name", ""), args=args))
            return ToolChatResponse(
                text=msg.get("content", "") or "",
                tool_calls=calls,
                tokens_in=data.get("prompt_eval_count", 0),
                tokens_out=data.get("eval_count", 0),
            )
        except Exception as exc:  # noqa: BLE001
            log.error("Ollama tool chat failed: %s", exc)
            return ToolChatResponse(error=f"Ollama error: {exc}")
