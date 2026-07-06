"""Voice pipeline — architecture in place, providers detected at runtime.

Design (docs/VOICE.md):
  mic → wake word ("Athena") → VAD → STT → chat pipeline → TTS → speaker

v1 ships the provider interfaces + availability detection. The app runs
fully without any voice deps; the UI voice panel shows "not configured".

Install path (all optional):
  STT:  pip install faster-whisper          (local Whisper)
  TTS:  Piper binary + voice model           (local TTS)
  Wake: pip install openwakeword             (train/download an "Athena" model)

Push-to-talk is the FIRST milestone (works before wake word is perfected):
POST audio bytes to /api/voice/transcribe → text → normal chat flow.
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]
PIPER_DIR = REPO_ROOT / "tools" / "piper"


class STTProvider(ABC):
    @abstractmethod
    def transcribe(self, audio_bytes: bytes, sample_rate: int = 16000) -> str: ...


class TTSProvider(ABC):
    @abstractmethod
    def synthesize(self, text: str) -> bytes:
        """Return WAV bytes."""
        ...


class FasterWhisperSTT(STTProvider):
    """Local Whisper via faster-whisper (CTranslate2). CPU int8 by default.

    The model is loaded lazily on the first transcribe call and cached for
    the process lifetime. First call downloads the model (~150 MB for
    `base`) to the Hugging Face cache; subsequent calls are offline.
    """

    def __init__(self, model_size: str = "base") -> None:
        self.model_size = model_size
        self._model = None

    def _load(self):
        if self._model is None:
            from faster_whisper import WhisperModel

            self._model = WhisperModel(
                self.model_size, device="cpu", compute_type="int8",
            )
        return self._model

    def transcribe(self, audio_bytes: bytes, sample_rate: int = 16000) -> str:
        import io

        model = self._load()
        # faster-whisper decodes webm/opus/wav/etc. itself via PyAV.
        segments, _info = model.transcribe(io.BytesIO(audio_bytes), beam_size=1)
        return " ".join(seg.text.strip() for seg in segments).strip()


_stt_singleton: FasterWhisperSTT | None = None


def get_stt() -> FasterWhisperSTT:
    """Process-wide STT instance so the model loads once."""
    global _stt_singleton
    if _stt_singleton is None:
        _stt_singleton = FasterWhisperSTT()
    return _stt_singleton


# TODO(cursor): PiperTTS(TTSProvider) — subprocess to piper.exe with a voice model.
# TODO(cursor): ElevenLabsTTS(TTSProvider) — network_access permission, API key from env.
# TODO(cursor): WakeWordListener — openwakeword loop, logs detections for the
#               "wake-word reliability" screen, toggled by wake_word_enabled setting.


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def voice_status() -> dict[str, Any]:
    """Availability report for the health screen and voice panel."""
    stt = _module_available("faster_whisper")
    wake = _module_available("openwakeword")
    piper = shutil.which("piper") is not None
    return {
        "configured": stt or piper,
        "stt": {"provider": "faster-whisper", "available": stt,
                "detail": "" if stt else "pip install faster-whisper"},
        "tts": {"provider": "piper", "available": piper,
                "detail": "" if piper else "Install Piper and add to PATH"},
        "wake_word": {"provider": "openwakeword", "available": wake,
                      "detail": "" if wake else "pip install openwakeword",
                      "phrase": "Athena"},
        "modes": ["push_to_talk", "conversation", "command"],
        "note": "Voice is optional — Athena runs fully without it.",
    }
