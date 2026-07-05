"""Remote Athena server provider — STUB for future server/hybrid mode.

Roadmap (docs/SERVER_ROADMAP.md): a hosted Athena backend exposes the same
API shape as this local one; this provider forwards chat to it, giving the
desktop app 'server-assisted' mode with zero UI changes. Auth is a bearer
token from env (ATHENA_SERVER_TOKEN) — replace with proper token storage
(Windows Credential Manager / OS keyring) before shipping server mode.
"""
from __future__ import annotations

from typing import AsyncIterator

from ..config import get_settings
from .base import ChatMessage, ModelProvider, ProviderStatus, StreamDelta


class RemoteAthenaProvider(ModelProvider):
    name = "athena-server"
    kind = "remote"

    async def status(self) -> ProviderStatus:
        url = get_settings().server_url
        if not url:
            return ProviderStatus(
                name=self.name, available=False, kind=self.kind,
                detail="No remote Athena server configured (future feature).",
            )
        # TODO(cursor): ping {url}/api/health with the auth token.
        return ProviderStatus(
            name=self.name, available=False, kind=self.kind,
            detail=f"Server URL set ({url}) but remote provider is not implemented yet.",
        )

    async def stream_chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncIterator[StreamDelta]:
        yield StreamDelta(
            done=True,
            error="Remote Athena server mode is not implemented yet (see docs/SERVER_ROADMAP.md).",
        )
