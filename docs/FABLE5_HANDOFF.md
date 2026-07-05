# Fable 5 Handoff

Context pack for premium-model sessions (Fable 5 / Claude) working on Athena.
Premium context is expensive — this file is the dense briefing so sessions
don't burn tokens rediscovering the system.

## System in five lines

1. Local-first assistant: FastAPI backend (`services/api`) + React desktop
   (`apps/desktop`) + manifest plugins (`plugins/`), SQLite+FTS5 storage.
2. Model calls go: chat → `routing/router.py` (classify → mode → budget/ask
   guardrails → availability) → `ModelProvider.stream_chat()` → SSE to UI.
3. Tools go through ONE gate: `plugins/executor.py` (permissions,
   confirmation queue, audit). Placeholders exist for voice/flow/qa/gmail/etc.
4. Memory: `memory/store.py`, categories + importance + modes, FTS search,
   compact `recall_block()` injection (never full dumps).
5. Invariants: runs with zero keys/deps (mock provider); no silent actions;
   secrets env-only; every routing decision carries a stored reason.

## When to use Fable 5 vs local (the router's own policy applies to you)

Use premium sessions for: architecture changes, the agent tool loop, the
QA agent rule engine, developer-mode change planner, tricky concurrency/
streaming bugs. Don't spend premium tokens on: renaming, CSS, boilerplate
CRUD, doc typos — local models or quick edits handle those.

## High-value work queue (same as CURSOR_HANDOFF.md, dense form)

1. Agent tool loop (executor is ready; wire model⇄tools⇄chat)
2. Memory extraction proposals (ask mode)
3. Fable5 provider: true SSE streaming
4. Voice push-to-talk (faster-whisper) → VOICE.md has exact steps
5. QA agent MVP → QA_AGENT_ROADMAP.md has the data model

## Contracts you must not break

- `StreamDelta`: errors inside the stream (`delta.error`), never raised
- `RoutingDecision.reason`: human-readable, always set, always stored
- Tool handlers: `(args: dict, ctx: ToolContext) -> dict`, `ToolError` for
  expected failures
- Permission levels: read_only / user_confirmed_write / system_sensitive /
  network_access / disabled — confirmation enforced only in the executor
- SSE event shapes documented at the top of `routers/chat.py`
