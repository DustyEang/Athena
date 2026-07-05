# Athena

**A local-first AI assistant platform** — voice-ready chat, memory, tools,
plugins, model routing, and project awareness. Built to grow from a Windows
desktop assistant into a personal AI operating layer with optional server
deployment.

<p align="center"><em>「 She should feel like an entity, not an app. 」</em></p>

## What Athena is

- **Chief of staff**: remembers your projects, preferences, and workflows
- **Model router**: local Ollama models by default, Fable 5 only for hard,
  high-value work — with cost tracking, budgets, and routing explanations
- **Tool hub**: plugin system with strict permission levels and user
  confirmation for anything sensitive
- **Project-aware**: workspaces for Flow, QA Agent, Business Ops, and more
- **Local-first**: runs fully offline with zero API keys (mock/local models)

## Quick start

```powershell
# 1. One-time setup (Python venv + npm install + .env)
.\scripts\setup.ps1

# 2. Start everything (backend on :8765, UI on :5173)
.\scripts\dev.ps1
```

Open http://localhost:5173. That's Athena. With no Ollama and no API key she
responds via the built-in mock provider — install [Ollama](https://ollama.com)
and `ollama pull llama3.1` for real local chat.

Full setup details: [docs/SETUP.md](docs/SETUP.md)

## Repo map

```
apps/desktop      React + Vite + Tailwind UI (Tauri scaffold included)
services/api      Python FastAPI backend (SQLite, providers, router, plugins)
packages/shared   Shared TypeScript API types
plugins/          Manifest-driven plugins (core, files, developer, + placeholders)
docs/             Architecture, roadmaps, handoff docs
scripts/          setup.ps1, dev.ps1
data/             Runtime data (SQLite DB, logs) — gitignored
tests/            Backend smoke tests (pytest)
```

## Documentation

| Doc | What |
|---|---|
| [SETUP.md](docs/SETUP.md) | Install & run, optional extras |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design, data flow, decisions |
| [ROADMAP.md](docs/ROADMAP.md) | Where Athena is going |
| [MODEL_ROUTER.md](docs/MODEL_ROUTER.md) | Routing rules, cost control, adding providers |
| [MEMORY.md](docs/MEMORY.md) | Memory categories, modes, search |
| [PLUGINS.md](docs/PLUGINS.md) | Plugin contract, permissions, how to add one |
| [SECURITY.md](docs/SECURITY.md) | Permission model, confirmations, audit |
| [VOICE.md](docs/VOICE.md) | Voice pipeline design & install path |
| [DEVELOPER_MODE.md](docs/DEVELOPER_MODE.md) | Safe self-development workflow |
| [FLOW_INTEGRATION.md](docs/FLOW_INTEGRATION.md) | Flow connector design |
| [QA_AGENT_ROADMAP.md](docs/QA_AGENT_ROADMAP.md) | Document review agent architecture |
| [SERVER_ROADMAP.md](docs/SERVER_ROADMAP.md) | Local → server → hybrid plan |
| [CURSOR_HANDOFF.md](docs/CURSOR_HANDOFF.md) | **Start here to continue development** |
| [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | Common problems |

## Status

v1 foundation. Chat, routing, memory, workspaces, plugins, settings, health,
and logs are real and tested. Voice, Flow, QA agent, and server mode are
clean architecture stubs. See [CURSOR_HANDOFF.md](docs/CURSOR_HANDOFF.md) for
exactly what's done vs stubbed.
