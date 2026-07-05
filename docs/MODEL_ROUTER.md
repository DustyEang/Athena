# Model Router

Files: `services/api/athena_api/routing/` and `providers/`.

## Routing pipeline

```
prompt ──► classify() ──► task mode ──► guardrails ──► availability ──► decision
           keyword        cheap/        budget cap,     fable5 down?     provider,
           heuristics     balanced/     ask-before-     ollama down?     model,
           → tier         max_power     premium         → fallback       REASON
```

Rules of thumb baked into the classifier:

| Signal | Route |
|---|---|
| simple chat, summarize, private/confidential | local |
| roadmap/strategy/SOP planning | premium |
| architecture / large codebase / refactor | premium |
| stack traces / complex debugging | premium |
| very large prompt (>~1.5k tokens) | premium (context) |
| user override `provider:model` | always wins |

Every decision has a `reason` string, shown in the chat UI and stored in the
`usage` table. **If routing ever surprises you, the explanation is right on
the message.**

## Cost control

- `ask_before_premium` (default **on**): premium routing emits
  `premium_confirmation_required` over SSE; the UI asks; resend with
  `confirm_premium: true`.
- `budget_monthly_usd` (default $20): premium is refused once the tracked
  month spend hits the cap — falls back to local with the reason logged.
- `task_mode`: `cheap` (never premium) / `balanced` / `max_power`.
- Context trimming: last 12 turns + summarized memory block, never full dumps.
- Token estimates: ~4 chars/token heuristic; Ollama returns real counts.
  Prices live in `routing/costs.py` → `PRICES` (update when pricing changes).

## Providers

| Provider | Kind | Status |
|---|---|---|
| `mock` | mock | always available (degraded mode + tests) |
| `ollama` | local | real streaming chat via Ollama API |
| `fable5` | premium | real Anthropic Messages API call (non-streaming v1) |
| `athena-server` | remote | stub for server mode |

## Adding a provider

1. `providers/myprovider.py` — subclass `ModelProvider`, implement `status()`
   and `stream_chat()` (yield `StreamDelta`s, final one `done=True`; put
   failures in `delta.error`, never raise through the stream).
2. Register in `providers/registry.py`.
3. Add pricing in `routing/costs.py` if it bills per token.
4. Done — the model selector, health screen, and router pick it up.

## Classifier upgrade path

`classifier.classify()` is one function. Swap the keyword heuristic for a
call to a small local model (e.g. ollama qwen2.5:0.5b with a JSON prompt)
when accuracy matters; keep the heuristic as fallback when Ollama is down.
