"""Voice endpoints — status is real; transcribe runs faster-whisper locally;
speak is an honest stub until Piper is installed (see voice/pipeline.py)."""
from __future__ import annotations

import anyio
from fastapi import APIRouter, HTTPException, Response, UploadFile
from pydantic import BaseModel

from ..voice.pipeline import get_stt, get_tts, voice_status

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


class SpeakRequest(BaseModel):
    text: str


MAX_SPEAK_CHARS = 2000  # keep replies snappy; long text is trimmed at a sentence


@router.post("/voice/speak")
async def speak(req: SpeakRequest):
    status = voice_status()
    if not status["tts"]["available"]:
        raise HTTPException(501, "TTS not configured. " + status["tts"]["detail"])
    text = req.text.strip()
    if not text:
        raise HTTPException(400, "Nothing to say.")
    if len(text) > MAX_SPEAK_CHARS:
        cut = text[:MAX_SPEAK_CHARS]
        text = cut[: cut.rfind(".") + 1] or cut
    try:
        wav = await anyio.to_thread.run_sync(get_tts().synthesize, text)
    except Exception as exc:
        raise HTTPException(500, f"Speech synthesis failed: {exc}") from exc
    return Response(content=wav, media_type="audio/wav")
