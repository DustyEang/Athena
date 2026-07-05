# Setup

## Prerequisites

| Requirement | Status | Notes |
|---|---|---|
| Windows 10/11 | required | primary target |
| Python 3.11+ | required | backend |
| Node.js 20+ | required | desktop UI |
| Git | recommended | developer tools |
| Ollama | optional | real local models — without it Athena uses the mock provider |
| Rust toolchain | optional | only for the Tauri native window (`npm run tauri:dev`) |
| Fable 5 API key | optional | premium routing — Athena runs fully without it |

## Install

```powershell
.\scripts\setup.ps1
```

This creates `.venv`, installs Python deps, runs `npm install`, and copies
`.env.example` → `.env`.

## Run

```powershell
.\scripts\dev.ps1          # backend + UI in two windows
# or individually:
.\scripts\dev-api.ps1      # backend only  → http://127.0.0.1:8765/docs
npm run dev:desktop        # UI only       → http://localhost:5173
```

## Verify

```powershell
.\.venv\Scripts\python -m pytest tests -q     # 11 smoke tests should pass
```

Then open the UI → **System** screen: database green, mock provider green,
Ollama/Fable 5 red until you configure them. That's healthy degraded mode.

## Optional: real local models

1. Install [Ollama](https://ollama.com/download/windows)
2. `ollama pull llama3.1` (or any model)
3. Restart nothing — Athena detects it live (System screen goes green)

## Optional: Fable 5 (premium)

1. Put your key in `.env`: `ATHENA_FABLE5_API_KEY=sk-ant-...`
2. Restart the backend
3. Settings → confirm "ask before premium" and your monthly budget

## Optional: voice (stubs today)

See [VOICE.md](VOICE.md). Short version: `pip install faster-whisper
openwakeword` + install Piper. The voice panel reports what's detected.

## Optional: native desktop window (Tauri)

1. Install Rust: https://rustup.rs (plus WebView2, preinstalled on Win 11)
2. `npm run tauri:dev` from the repo root

Until then, browser dev mode at :5173 is byte-for-byte the same app.
