# Security & Permissions

## Principles

1. **Athena never acts silently.** Every tool run is recorded; sensitive ones
   pause for explicit user approval first.
2. **Deny by default.** Risky tools ship disabled (`run_command`), risky
   plugins ship disabled (gmail, smart_home, …), file access requires an
   explicit folder grant.
3. **Secrets live in the environment.** API keys come from `.env`/env vars;
   the settings API exposes only *configured / not configured*, never values.
   Nothing in the repo or DB contains a key.

## Enforcement points

| Boundary | Where |
|---|---|
| Tool permission levels + confirmation queue | `plugins/executor.py` (single choke point) |
| Folder access grants (read) | `routers/files.py` + `_require_granted` in file/dev plugins — paths are `resolve()`d so `..`/symlinks can't escape |
| Writes/deletes/commands/launches | `user_confirmed_write` / `system_sensitive` → UI approval |
| App launcher | settings-controlled allowlist, no arguments, no shell |
| Premium model spend | ask-before-premium + monthly budget in the router |
| Audit trail | `audit_log` table + `tool_runs` + rotating file logs |

## Sensitive actions that always require confirmation

Delete/modify files · run commands · install packages · send email · modify
calendar · costed external API calls · uploading local data to premium models
(ask-before-premium) · launching apps · smart home actions.

## Known gaps (be honest, fix in order)

1. **No API auth on the backend.** Fine while it binds to localhost for one
   user; **mandatory before server mode** (bearer tokens minimum — see
   SERVER_ROADMAP.md).
2. CORS allows the dev origins only, but any local process can call the API.
   Same fix as #1 (local token handshake between app and backend).
3. Token storage plan for server mode: Windows Credential Manager via keyring,
   not files.
4. `run_command` uses `shell=True` when enabled — it is disabled by default
   and confirmation-gated, but consider arg-vector execution + allowlist
   before enabling it routinely.
