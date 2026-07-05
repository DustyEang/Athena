"""Voice endpoints — status is real; transcribe runs faster-whisper locally;
speak is an honest stub until Piper is installed (see voice/pipeline.py)."""
from __future__ import annotations

import anyio
from fastapi import APIRouter, HTTPException, UploadFile

from ..voice.pipeline import get_stt, voice_status

router = APIRouter(tags=["voice"])

MAX_AUDIO_BYTES = 25 * 1024 * 1024  # ~25 MB ≈ several minutes of opus


@router.get("/voice/status")
def get_voice_status():
    return voice_status()


@router.post("/voice/transcribe")
async def transcribe(audio: UploadFile):
    status = voice_status()
    if not status["stt"]["available"]:
        raise HTTPException(501, "STT not configured. " + status["stt"]["detail"])
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(400, "Empty audio upload.")
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise HTTPException(413, "Audio too large — keep recordings under a few minutes.")
    try:
        # Model inference is CPU-bound; keep the event loop responsive.
        text = await anyio.to_thread.run_sync(get_stt().transcribe, audio_bytes)
    except Exception as exc:  # decode failures, model load errors
        raise HTTPException(500, f"Transcription failed: {exc}") from exc
    return {"text": text}


@router.post("/voice/speak")
def speak():
    status = voice_status()
    if not status["tts"]["available"]:
        raise HTTPException(501, "TTS not configured. " + status["tts"]["detail"])
    # TODO(cursor): accept {"text": ...}, return audio/wav via PiperTTS
    raise HTTPException(501, "TTS provider detected but pipeline not wired yet (v1 stub).")
