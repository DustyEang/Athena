# Troubleshooting

**UI says "backend offline"** — Start it: `.\scripts\dev-api.ps1`. Check
http://127.0.0.1:8765/api/health in a browser. If another process owns port
8765: `netstat -ano | findstr 8765`, then change `ATHENA_API_PORT` in `.env`
*and* `API_BASE` in `apps/desktop/src/lib/api.ts`.

**Chat answers with "Mock provider response"** — Working as designed: no
real model is reachable. Install Ollama + `ollama pull llama3.1`, or set
`ATHENA_FABLE5_API_KEY`. System screen shows live provider status.

**Ollama installed but red on System screen** — Is `ollama serve` running?
Default URL is `http://localhost:11434` (`ATHENA_OLLAMA_URL` to change).
`curl http://localhost:11434/api/tags` should return JSON.

**Fable 5 configured but every request stays local** — Check, in order:
(1) Settings → task mode isn't `cheap`; (2) monthly budget not exhausted
(System screen shows spend); (3) the routing reason on the message — it
tells you exactly why.

**`pytest` fails on FTS5** — Your Python's sqlite3 lacks FTS5 (rare;
python.org builds have it). `python -c "import sqlite3;
sqlite3.connect(':memory:').execute('CREATE VIRTUAL TABLE t USING fts5(c)')"`.

**File tools refuse every path** — Expected: grant the folder first
(`POST /api/files/grants`), then index it. Grants survive restarts.

**Tool stuck "pending_confirmation"** — By design; approve/deny it in the
chat sidebar's Tool activity feed, or `POST /api/tools/confirm/{id}`.

**`npm run tauri:dev` fails** — Rust isn't installed (https://rustup.rs).
Browser mode (`npm run dev:desktop`) is the same app meanwhile.

**Voice endpoints return 501** — Correct for v1: stubs report not-configured.
See docs/VOICE.md for the install path.

**Where is everything?** — DB: `data/athena.db` · logs: `data/logs/athena.log`
+ Logs screen · audit: `GET /api/tools/audit` · API docs:
http://127.0.0.1:8765/docs (interactive Swagger).

**Reset Athena completely** — Stop backend, delete `data/athena.db*`,
restart. Workspaces reseed; memory/settings/usage are gone.
