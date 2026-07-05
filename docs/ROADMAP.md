# Roadmap

## v1 — Foundation (this build) ✅
Chat with streaming + cost-aware routing (mock/Ollama/Fable 5), memory with
categories/modes/search + UI, workspaces (seeded with your projects), plugin
framework with permissions + confirmations + audit, file grants/indexing/
search, settings, health, logs, docs, tests. Voice/Flow/QA/server as clean
stubs.

## v1.1 — Make her useful daily
- **Agent loop**: model can request tools mid-chat (executor is ready);
  confirmation cards appear inline in chat
- Memory extraction with `ask` mode proposals
- Model-powered document summarization (local model via router)
- Real Ollama embedding + Chroma vector recall
- Conversation history UI (list + resume)

## v1.2 — Voice
- Push-to-talk: mic capture in UI → `/voice/transcribe` (faster-whisper)
- Piper TTS responses; orb speaking state driven by playback
- Wake word "Athena" via openwakeword + reliability log
- Conversation vs command mode

## v1.3 — Developer mode for real
- Change planner → diff review → approve → apply → changelog
- Git checkpoint/rollback strategy
- Test runner integration

## v2 — Flow + QA Agent
- Flow API connector (all 9 placeholder tools)
- QA agent MVP: SOP rules + chart lookup + scoring + report (see
  QA_AGENT_ROADMAP.md)

## v3 — Server & multi-device
- Dockerized backend + auth → server-assisted mode
- Job queue for heavy work; memory sync
- Web dashboard; mobile client notes in SERVER_ROADMAP.md
