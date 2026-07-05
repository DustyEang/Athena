"""Voice endpoints — status is real; transcribe/speak are honest stubs
that return 501 until voice deps are installed (see voice/pipeline.py)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..voice.pipeline import voice_status

router = APIRouter(tags=["voice"])


@router.get("/voice/status")
def get_voice_status():
    return voice_status()


@router.post("/voice/transcribe")
def transcribe():
    status = voice_status()
    if not status["stt"]["available"]:
        raise HTTPException(501, "STT not configured. " + status["stt"]["detail"])
    # TODO(cursor): accept multipart audio, run FasterWhisperSTT, return {"text": ...}
    raise HTTPException(501, "STT provider detected but pipeline not wired yet (v1 stub).")


@router.post("/voice/speak")
def speak():
    status = voice_status()
    if not status["tts"]["available"]:
        raise HTTPException(501, "TTS not configured. " + status["tts"]["detail"])
    # TODO(cursor): accept {"text": ...}, return audio/wav via PiperTTS
    raise HTTPException(501, "TTS provider detected but pipeline not wired yet (v1 stub).")
