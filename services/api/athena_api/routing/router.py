"""Cost-aware model router.

Selection order for each request:
1. Explicit user override ("provider:model") always wins.
2. Classify the task (classifier.py) → local vs premium tier.
3. Task mode setting shifts the tier: cheap forces local, max_power prefers
   premium when available, balanced trusts the classifier.
4. Guardrails can veto premium: budget limit reached, or the
   ask_before_premium setting (returns needs_premium_confirmation so the UI
   can ask; the frontend re-sends with confirm_premium=true).
5. Availability fallback: premium unavailable → local; Ollama down → mock.

Every decision carries a human-readable `reason` — shown in the UI and
stored with usage so the user can audit why Athena spent (or saved) money.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from ..config import get_settings
from ..db import get_setting
from ..providers import get_provider_registry
from .classifier import classify
from .costs import month_spend


@dataclass
class RoutingDecision:
    provider: str
    model: str
    task_type: str
    reason: str
    tier: str                             # local | premium | mock
    needs_premium_confirmation: bool = False
    warnings: list[str] = field(default_factory=list)


async def _local_choice() -> tuple[str, str, str]:
    """Best available local option: (provider, model, note)."""
    registry = get_provider_registry()
    ollama = await registry.get("ollama").status()
    if ollama.available:
        settings = get_settings()
        model = (
            settings.ollama_default_model
            if settings.ollama_default_model in ollama.models or not ollama.models
            else ollama.models[0]
        )
        return "ollama", model, "local Ollama model"
    return "mock", "athena-mock", "Ollama unavailable → mock fallback"


async def route_request(
    conn: sqlite3.Connection,
    prompt: str,
    model_override: str | None = None,
    confirm_premium: bool = False,
) -> RoutingDecision:
    registry = get_provider_registry()

    # 1. Manual override: "provider:model" (e.g. "ollama:llama3.1", "fable5:claude-fable-5")
    if model_override:
        provider_name, _, model = model_override.partition(":")
        provider = registry.get(provider_name)
        if provider is None:
            return RoutingDecision("mock", "athena-mock", "chat",
                                   f"unknown provider '{provider_name}' → mock", "mock",
                                   warnings=[f"Unknown provider '{provider_name}'"])
        status = await provider.status()
        if not status.available:
            fb_provider, fb_model, note = await _local_choice()
            return RoutingDecision(fb_provider, fb_model, "chat",
                                   f"requested {provider_name} unavailable → {note}",
                                   "local" if fb_provider == "ollama" else "mock",
                                   warnings=[status.detail])
        return RoutingDecision(
            provider_name, model or (status.models[0] if status.models else ""),
            "chat", "manual model selection by user",
            "premium" if provider.kind == "premium" else provider.kind,
        )

    # 2-3. Classify, then apply task mode
    cls = classify(prompt)
    mode = get_setting(conn, "task_mode", "balanced")  # cheap | balanced | max_power
    tier = cls.tier
    reason = cls.reason
    if mode == "cheap" and tier == "premium":
        tier, reason = "local", f"{cls.reason}; but task mode 'cheap' forces local"
    elif mode == "max_power" and tier == "local":
        tier, reason = "premium", f"{cls.reason}; task mode 'max power' prefers premium"

    # 4-5. Premium guardrails + availability
    if tier == "premium":
        fable5 = await registry.get("fable5").status()
        if fable5.available:
            budget = float(get_setting(conn, "budget_monthly_usd", 20.0))
            spent = month_spend(conn)
            if spent >= budget:
                tier, reason = "local", (
                    f"{reason}; BUT monthly budget reached "
                    f"(${spent:.2f} of ${budget:.2f}) → staying local"
                )
            elif get_setting(conn, "ask_before_premium", True) and not confirm_premium:
                return RoutingDecision(
                    "fable5", get_settings().fable5_model, cls.task_type,
                    f"{reason}; awaiting user approval for premium model",
                    "premium", needs_premium_confirmation=True,
                )
            else:
                return RoutingDecision("fable5", get_settings().fable5_model,
                                       cls.task_type, reason, "premium")
        else:
            reason = f"{reason}; premium unavailable ({fable5.detail}) → local"

    provider, model, note = await _local_choice()
    return RoutingDecision(
        provider, model, cls.task_type, f"{reason}; using {note}",
        "local" if provider == "ollama" else "mock",
    )
