"""Provider registry — single place where providers are wired in."""
from __future__ import annotations

from functools import lru_cache

from .base import ModelProvider, ProviderStatus
from .fable5 import Fable5Provider
from .mock import MockProvider
from .ollama import OllamaProvider
from .remote import RemoteAthenaProvider


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, ModelProvider] = {}
        for provider in (MockProvider(), OllamaProvider(), Fable5Provider(), RemoteAthenaProvider()):
            self._providers[provider.name] = provider
        # TODO(cursor): register OpenAI / Gemini / custom-HTTP providers here.

    def get(self, name: str) -> ModelProvider | None:
        return self._providers.get(name)

    def all(self) -> list[ModelProvider]:
        return list(self._providers.values())

    async def statuses(self) -> list[ProviderStatus]:
        return [await p.status() for p in self.all()]


@lru_cache
def get_provider_registry() -> ProviderRegistry:
    return ProviderRegistry()
