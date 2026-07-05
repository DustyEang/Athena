"""Mock provider — always available so Athena runs with zero external deps.

Used automatically when Ollama isn't running and no premium key is set.
Also handy for UI development and tests.

Tool calling: supported via an explicit directive so the agent loop is
testable without any model. If the last user message contains
    !tool plugin.tool {"json": "args"}
the mock "decides" to call that tool, then summarizes the result.
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import AsyncIterator

from .base import (
    AgentTurn, ChatMessage, ModelProvider, ProviderStatus, StreamDelta,
    ToolCallRequest, ToolChatResponse, ToolSpec, estimate_tokens,
)

_DIRECTIVE = re.compile(r"!tool\s+([\w-]+)\.([\w-]+)\s*(\{.*\})?", re.DOTALL)


def _mock_reply(last_user: str) -> str:
    return (
        "⚠ Mock provider response — no real model is connected yet.\n\n"
        f'You said: "{last_user[:400]}"\n\n'
        "To get real answers: start Ollama (`ollama serve`, then pull a model), "
        "or add a Fable 5 API key in Settings. Athena will route to real "
        "providers automatically once one is available."
    )


class MockProvider(ModelProvider):
    name = "mock"
    kind = "mock"
    supports_tools = True

    async def status(self) -> ProviderStatus:
        return ProviderStatus(
            name=self.name,
            available=True,
            kind=self.kind,
            detail="Built-in mock provider (no external model needed).",
            models=["athena-mock"],
        )

    async def stream_chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncIterator[StreamDelta]:
        last_user = next((m.content for m in reversed(messages) if m.role == "user"), "")
        reply = _mock_reply(last_user)
        tokens_in = sum(estimate_tokens(m.content) for m in messages)
        for word in reply.split(" "):
            await asyncio.sleep(0.01)  # simulate streaming for UI development
            yield StreamDelta(text=word + " ")
        yield StreamDelta(done=True, tokens_in=tokens_in, tokens_out=estimate_tokens(reply))

    async def chat_with_tools(
        self,
        turns: list[AgentTurn],
        model: str,
        tools: list[ToolSpec],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> ToolChatResponse:
        tokens_in = sum(estimate_tokens(t.content) for t in turns)
        last_user = next((t.content for t in reversed(turns) if t.role == "user"), "")

        # If we already returned a tool result this conversation step,
        # produce a closing summary instead of looping forever.
        if turns and turns[-1].role == "tool":
            text = f"(mock) Tool finished. Result: {turns[-1].content[:300]}"
            return ToolChatResponse(text=text, tokens_in=tokens_in,
                                    tokens_out=estimate_tokens(text))

        match = _DIRECTIVE.search(last_user)
        if match:
            plugin, tool, raw_args = match.groups()
            name = f"{plugin}__{tool}"
            if any(t.name == name for t in tools):
                try:
                    args = json.loads(raw_args) if raw_args else {}
                except json.JSONDecodeError:
                    args = {}
                return ToolChatResponse(
                    text=f"(mock) Calling {plugin}.{tool}…",
                    tool_calls=[ToolCallRequest(id="mock-call-1", name=name, args=args)],
                    tokens_in=tokens_in, tokens_out=8,
                )
            text = f"(mock) Tool {plugin}.{tool} is not available to me."
            return ToolChatResponse(text=text, tokens_in=tokens_in,
                                    tokens_out=estimate_tokens(text))

        text = _mock_reply(last_user)
        return ToolChatResponse(text=text, tokens_in=tokens_in,
                                tokens_out=estimate_tokens(text))
