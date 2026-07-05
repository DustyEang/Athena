# Server Roadmap

Athena is local-first forever; server mode is an *addition*, never a
requirement. Offline fallback to local models is a design invariant.

## Modes

| Mode | What runs where | Status |
|---|---|---|
| `local` | everything on the Windows machine | **today** |
| `server_assisted` | desktop UI + local backend; heavy tasks forwarded to a remote Athena backend via the `athena-server` provider | stubbed |
| `cloud_orchestrated` | server owns router, plugins, memory, job queue; desktop/web/mobile are thin clients | designed |

The `server_mode` setting + `ATHENA_SERVER_URL`/`ATHENA_SERVER_TOKEN` env
vars already exist. `providers/remote.py` is the integration point — the
remote server exposes the *same API shape* as the local backend, so the
desktop app needs no changes.

## Docker (backend is containerizable today)

`services/api/Dockerfile` is included. Compose sketch for a GPU server:

```yaml
services:
  athena-api:   # this repo's backend
    build: ./services/api
    ports: ["8765:8765"]
    volumes: ["athena-data:/data"]
    environment: [ATHENA_DATA_DIR=/data, ATHENA_OLLAMA_URL=http://ollama:11434]
  ollama:
    image: ollama/ollama
    # deploy.resources.reservations.devices for GPU
volumes: { athena-data: }
```

## Before exposing anything remotely (order matters)

1. **Auth**: bearer token middleware on FastAPI (`Authorization: Bearer`),
   tokens stored client-side in Windows Credential Manager (python `keyring`)
   — never in files. This is gap #1 in SECURITY.md.
2. TLS termination (Caddy/Traefik) — never plain HTTP off-box.
3. Job queue for heavy work (QA batches, indexing): start with a SQLite jobs
   table + worker process; graduate to Redis/RQ only when needed.
4. Memory sync: last-write-wins per memory id is acceptable v1; the
   `server_connector.sync_memory` tool is the hook.

## Future clients

- **Web dashboard**: reuse `packages/shared` types; the API is already
  CORS-ready — add the dashboard origin.
- **Mobile**: same API; voice becomes the primary interface there.
