# Cursor Handoff

You are inheriting **Athena v1 foundation** — a working, tested, local-first
AI assistant platform. This doc is your map. Read ARCHITECTURE.md next.

## What was built (and verified)

- **Backend** (`services/api`): FastAPI + SQLite(FTS5). Chat with SSE
  streaming; cost-aware model router with explanations; providers: mock
  (always), Ollama (real), Fable 5 (real Anthropic API call when key set),
  remote-server (stub); memory with categories/importance/modes + FTS search;
  workspaces (seeded); plugin registry + permission/confirmation executor +
  audit log; file grants/indexing/search; settings; health; ring-buffer logs.
  **11 pytest smoke tests pass in full degraded mode.**
- **Desktop** (`apps/desktop`): React+Vite+Tailwind v4, zustand. Views: Chat
  (orb, streaming, routing badges, premium-confirm banner, tool feed with
  approve/deny), Memory, Workspaces, Plugins, System, Logs, Settings.
  Builds clean (`npm run build:desktop`). Tauri scaffold present; needs Rust
  installed for native window — browser dev mode is identical.
- **Plugins** (`plugins/`): core/files/developer implemented; voice, flow,
  qa_agent, web_search, gmail, calendar, smart_home, business,
  server_connector are honest placeholders (manifest contracts, no handlers).

## Run / verify

```powershell
.\scripts\setup.ps1     # once
.\scripts\dev.ps1       # backend :8765 + UI :5173
.\.venv\Scripts\python -m pytest tests -q    # must stay green
```

## Do NOT rewrite

- The **provider ABC** (`providers/base.py`) and **registry** — add providers, don't reshape the interface
- The **plugin executor** (`plugins/executor.py`) — it is the single security
  choke point; never let a tool bypass it
- The **routing decision + reason** pattern — every model choice must stay
  explainable and recorded in `usage`
- The **degraded-mode invariant** — the app must always run with zero keys,
  zero Ollama, zero voice deps
- SQLite/FTS5 as the base store (add Chroma alongside via `memory/vector.py`,
  don't replace)

## Tier 1 upgrade (2026-07-02, second pass) — DONE

- **Agent tool loop is LIVE**: providers expose `chat_with_tools()`
  (mock scripted, Ollama + Fable 5 native tool calling); `agent/loop.py`
  runs up to 5 steps through the permission-checked executor; SSE emits
  `tool_call`/`tool_result`; chat UI renders inline tool chips.
  Confirmation-gated tools become pending runs — the model is told to wait.
- **Memory extraction**: `memory/extractor.py` runs post-chat on the LOCAL
  model only; `ask` mode creates pending proposals (excluded from recall
  until approved); Memory UI has an "Athena wants to remember" approval card.
- **Semantic recall**: `memory/vector.py` — nomic-embed-text via Ollama,
  float32 BLOBs in SQLite, cosine + reciprocal-rank fusion with FTS.
  Degrades to FTS-only when the embed model is missing.
- Schema v2 migration pattern established in `db.py` (MIGRATIONS dict).
- Test suite now 15 tests, all passing.

## Known incomplete (in priority order)

1. Voice push-to-talk — see VOICE.md, exact steps (next "wow" milestone)
2. Fable 5 SSE streaming (currently single-shot) — providers/fable5.py TODO
3. Conversation history UI (backend endpoints exist: `/api/chat/conversations`)
4. Model-powered summarize_document (currently extractive)
5. Developer-mode change planner (contract in DEVELOPER_MODE.md)
6. Flow handlers (FLOW_INTEGRATION.md), QA agent (QA_AGENT_ROADMAP.md)
7. Backend auth before any server exposure (SECURITY.md gap #1)
8. Agent-loop niceties: parallel tool calls, per-workspace tool allowlists,
   streaming the final agent answer token-by-token

## Conventions

- Python: type hints, pydantic models per router, `logging.getLogger("athena.*")`,
  raise `ToolError` for user-facing tool failures; never swallow exceptions
- TS: strict mode, shared API types in `packages/shared/src/types.ts` updated
  with any schema change; views under `src/views`, one file per screen
- Secrets: env only. Adding a key = `.env.example` + `config.py`, never code/DB
- New tool = manifest entry + handler + (if sensitive) correct permission
  level; the executor handles the rest
- Tests: extend `tests/test_api.py`; keep everything runnable degraded

## Common commands

```powershell
.\scripts\dev-api.ps1                        # backend only (hot reload)
npm run dev:desktop                          # UI only
npm run build:desktop                        # type-check + build
npm run tauri:dev                            # native window (needs Rust)
.\.venv\Scripts\python -m pytest tests -q    # backend tests
```

## Suggested first prompt in Cursor

> Read docs/CURSOR_HANDOFF.md and docs/ARCHITECTURE.md. Then implement the
> agent tool loop: when a model response requests a tool call, route it
> through the existing plugin executor (`plugins/executor.py`) with its
> permission/confirmation flow, feed the result back to the model, and
> render tool calls + confirmations inline in the chat UI. Start with the
> Ollama provider using its tool-calling format, keep the mock provider
> working, add a pytest covering a read_only tool round-trip, and do not
> modify the executor's security behavior.
