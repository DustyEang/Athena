"""Model provider interface.

To add a provider (OpenAI, Gemini, remote Athena server, custom HTTP):
1. Subclass ModelProvider, implement `status()` and `stream_chat()`.
2. If the model supports native tool calling, set `supports_tools = True`
   and implement `chat_with_tools()` (used by the agent loop).
3. Register it in registry.py.
4. Add pricing to routing/costs.py if it bills per token.
Nothing else in the codebase needs to change — the router, chat endpoint,
and agent loop only speak this interface.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator


@dataclass
class ChatMessage:
    role: str  # system | user | assistant
    content: str


@dataclass
class StreamDelta:
    """One streamed chunk. `done=True` carries final token counts."""
    text: str = ""
    done: bool = False
    tokens_in: int = 0
    tokens_out: int = 0
    error: str = ""


# ---------- Tool calling (agent loop) ----------

@dataclass
class ToolSpec:
    """A tool offered to the model. `name` is 'plugin__tool' (double
    underscore — safe in every provider's function-name charset)."""
    name: str
    description: str
    input_schema: dict


@dataclass
class ToolCallRequest:
    """Model asked to run a tool."""
    id: str
    name: str          # 'plugin__tool'
    args: dict


@dataclass
class AgentTurn:
    """Provider-agnostic conversation turn for tool-enabled chats.
    Providers convert this to their native wire format."""
    role: str                                   # system | user | assistant | tool
    content: str = ""
    tool_calls: list[ToolCallRequest] = field(default_factory=list)  # assistant only
    tool_call_id: str = ""                      # tool role only


@dataclass
class ToolChatResponse:
    """One non-streaming model step in the agent loop."""
    text: str = ""
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    tokens_in: int = 0
    tokens_out: int = 0
    error: str = ""


@dataclass
class ProviderStatus:
    name: str
    available: bool
    kind: str  # local | premium | remote | mock
    detail: str = ""
    models: list[str] = field(default_factory=list)


class ModelProvider(ABC):
    name: str = "base"
    kind: str = "local"  # local | premium | remote | mock
    supports_tools: bool = False

    @abstractmethod
    async def status(self) -> ProviderStatus: ...

    @abstractmethod
    def stream_chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncIterator[StreamDelta]:
        """Yield StreamDelta chunks; final chunk must have done=True.
        On failure, yield a single delta with `error` set — never raise
        through the SSE stream."""
        ...

    async def chat_with_tools(
        self,
        turns: list[AgentTurn],
        model: str,
        tools: list[ToolSpec],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> ToolChatResponse:
        """One agent-loop step: model sees the turns + tools, returns either
        text, tool calls, or both. Non-streaming by design (loop steps are
        short). Errors go in `.error`, never raised."""
        return ToolChatResponse(error=f"{self.name} does not support tool calling")


def estimate_tokens(text: str) -> int:
    """Cheap heuristic (~4 chars/token). Good enough for cost guardrails;
    replace with a real tokenizer if budgets need precision."""
    return max(1, len(text) // 4)
