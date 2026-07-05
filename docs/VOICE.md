# Voice

State: **architecture + detection implemented, pipeline stubbed.** The app
runs fully without voice; the System screen and voice endpoints report
exactly what's missing.

## Target pipeline

```
mic → wake word ("Athena") → VAD → STT (faster-whisper) → chat/router
                                     ↓
speaker ← TTS (Piper local / ElevenLabs optional) ← response
```

Orb states are already wired in the UI: idle / listening / thinking /
speaking (`useAppStore.setOrbState`).

## Implementation order (do it in this order — push-to-talk first)

1. **Push-to-talk (v1.2 milestone)**
   - UI: hold the 🎙 button → `MediaRecorder` captures webm/opus
   - Backend: `POST /voice/transcribe` (multipart) → faster-whisper
     (`pip install faster-whisper`, lazy-load `base` model, CPU int8 is fine)
   - Drop transcript into the chat composer for correction before send
2. **TTS**: `POST /voice/speak {text}` → Piper subprocess → WAV response →
   `Audio` playback; orb speaking during playback; per-response mute toggle
3. **Wake word**: openwakeword loop in a background thread; log every
   detection to the wake-word reliability log (`voice` plugin tool);
   `wake_word_enabled` setting gates it
4. **VAD + conversation mode**: webrtcvad or silero; command mode = single
   utterance, conversation mode = continuous until "thanks Athena"/timeout

## Settings already present

`voice_enabled`, `wake_word_enabled` (Settings UI), plus plugin settings in
`plugins/voice/manifest.json`: wake word phrase, personality, audio devices.

## Rules

- Voice is never mandatory; every failure degrades to text chat
- STT runs locally by default (privacy); external TTS is opt-in
  `network_access` with its own provider class
