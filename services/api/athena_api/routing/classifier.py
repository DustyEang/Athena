"""Task classification — decides what *kind* of work a prompt is.

v1 is a transparent keyword heuristic (fast, free, debuggable). The
interface is one function so it can later be swapped for a small local
model call without touching the router.

Task types map to tiers in router.py:
  chat / summarize / private        -> local tier
  plan / architecture / debug / code -> premium tier (if allowed)
"""
from __future__ import annotations

from dataclasses import dataclass

_PREMIUM_HINTS: dict[str, list[str]] = {
    "plan": ["roadmap", "strategy", "plan out", "milestones", "business plan", "sop"],
    "architecture": ["architecture", "refactor", "codebase", "monorepo", "system design", "schema design"],
    "debug": ["stack trace", "traceback", "exception", "doesn't work", "keeps failing", "root cause", "debug"],
    "code": ["write a function", "implement", "unit test", "regex", "algorithm"],
}
_LOCAL_HINTS: dict[str, list[str]] = {
    "summarize": ["summarize", "summary", "tl;dr", "shorten", "key points"],
    "private": ["password", "ssn", "private", "confidential", "do not upload"],
}


@dataclass
class Classification:
    task_type: str          # chat | summarize | private | plan | architecture | debug | code
    tier: str               # local | premium
    long_context: bool      # prompt is big enough to matter for context-window routing
    reason: str


def classify(prompt: str) -> Classification:
    lower = prompt.lower()
    long_context = len(prompt) > 6000  # ~1.5k tokens; heuristic

    for task, hints in _LOCAL_HINTS.items():
        if any(h in lower for h in hints):
            return Classification(task, "local", long_context,
                                  f"matched '{task}' keywords → keep local")

    for task, hints in _PREMIUM_HINTS.items():
        if any(h in lower for h in hints):
            return Classification(task, "premium", long_context,
                                  f"matched '{task}' keywords → high-value task")

    if long_context:
        return Classification("chat", "premium", True,
                              "very large prompt → bigger context window helps")

    return Classification("chat", "local", False, "simple chat → local model is enough")
