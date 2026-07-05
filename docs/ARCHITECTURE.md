# Architecture

## System overview

```
┌────────────────────────── Desktop (apps/desktop) ─────────────────────────┐
│ React + Vite + Tailwind · zustand state · SSE chat client                 │
│ Views: Chat/Orb · Memory · Workspaces · Plugins · System · Logs · Settings│
│ (Tauri shell scaffolded; browser dev mode identical)                      │
└─────────────────────────────────┬──────────────────────────────────────────┘
                                  │ HTTP + SSE (localhost:8765)
┌─────────────────────────────────▼──────────────── services/api ───────────┐
│ FastAPI                                                                   │
│  routers/   chat models memory settings tools plugins voice health logs   │
│             workspaces files developer                                    │
│  routing/   classifier (task type) → router (cost-aware) → costs (track)  │
│  providers/ mock · ollama · fable5 · remote-athena   [ModelProvider ABC]  │
│  memory/    MemoryStore (FTS5) · VectorStore interface (Chroma later)     │
│  plugins/   registry (manifest scan) · executor (permissions+confirm)     │
│  voice/     pipeline interfaces + runtime availability detection          │
└─────────────────────────────────┬──────────────────────────────────────────┘
                                  │
                     SQLite (data/athena.db, WAL, FTS5)
                                  │
                 plugins/*  ← manifest.json + handler.py, loaded dynamically
```

## Key decisions & why

**SQLite stdlib, no ORM.** Zero install friction, WAL is plenty for a
single-user local app, FTS5 gives real search for free. Migration path:
bump `SCHEMA_VERSION` in `db.py`.

**FTS5 before vectors.** Keyword search works day one with no model
downloads. `memory/vector.py` defines the `VectorStore` interface so Chroma +
local embeddings drop in without touching callers.

**Providers are an ABC, routing is a pure function.** `route_request()`
returns a `RoutingDecision` with a human-readable reason. Every decision is
stored with usage. Nothing else knows provider details.

**Plugins are data + code, not code alone.** `manifest.json` declares tools,
permissions, and settings; `handler.py` implements them. Placeholders are
manifests without handlers — visible in the UI, honest at runtime. The
executor is the single choke point for permissions, confirmation, and audit.

**Degraded mode is a feature.** Mock provider always exists; every external
dependency (Ollama, Fable 5, voice, Rust) is detected, reported, and optional.

**SSE over WebSockets.** Chat streaming is one-directional; SSE is simpler,
proxy-friendly, and trivially consumed with `fetch`. Revisit if server mode
needs bidirectional (voice streaming likely will → WebSocket then).

## Data flow: one chat message

1. UI POSTs `/api/chat` → user message persisted.
2. `route_request`: classify → apply task mode → budget/ask-premium
   guardrails → availability fallback. Emits `routing` SSE event (visible in
   the UI as the provider badge + reason).
3. Prompt assembly: system prompt + **summarized** memory recall (top-5 FTS
   hits, capped chars — never a full dump) + last 12 turns.
4. Provider streams deltas → UI renders live; orb goes thinking → speaking.
5. On done: assistant message + token/cost usage persisted (fresh connection,
   since the stream outlives the request scope).

## Databases tables

`workspaces conversations messages memories(+fts) usage tool_runs audit_log
folder_grants file_chunks(+fts) plugin_state app_settings meta` — see
`services/api/athena_api/db.py` (schema is the documentation).

## Where things will grow

- **Server mode**: same FastAPI app in Docker; desktop points at it via the
  `athena-server` provider. See SERVER_ROADMAP.md.
- **Agent loop**: chat → model requests tool → executor (confirm if needed) →
  result back to model. The executor and tool schemas are already shaped for
  this; the loop itself is the next big milestone (CURSOR_HANDOFF.md).
- **Voice**: pipeline interfaces exist; push-to-talk first, wake word later.
