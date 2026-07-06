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


def find_piper() -> str | None:
    """Locate piper.exe: env override → repo tools/ → PATH."""
    env_path = os.environ.get("ATHENA_PIPER_PATH")
    if env_path and Path(env_path).is_file():
        return env_path
    bundled = PIPER_DIR / "piper.exe"
    if bundled.is_file():
        return str(bundled)
    return shutil.which("piper")


def find_piper_voice() -> str | None:
    """Locate a voice model: env override → first .onnx in tools/piper/voices."""
    env_voice = os.environ.get("ATHENA_PIPER_VOICE")
    if env_voice and Path(env_voice).is_file():
        return env_voice
    voices_dir = PIPER_DIR / "voices"
    if voices_dir.is_dir():
        for onnx in sorted(voices_dir.glob("*.onnx")):
            return str(onnx)
    return None


class PiperTTS(TTSProvider):
    """Local TTS via the Piper binary. Writes to a temp WAV and returns bytes."""

    def __init__(self, piper_path: str, voice_path: str) -> None:
        self.piper_path = piper_path
        self.voice_path = voice_path

    def synthesize(self, text: str) -> bytes:
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "speech.wav"
            proc = subprocess.run(
                [self.piper_path, "--model", self.voice_path,
                 "--output_file", str(out_path)],
                input=text.encode("utf-8"),
                capture_output=True,
                timeout=120,
            )
            if proc.returncode != 0 or not out_path.is_file():
                raise RuntimeError(
                    f"piper failed (rc={proc.returncode}): "
                    f"{proc.stderr.decode('utf-8', 'replace')[-300:]}"
                )
            return out_path.read_bytes()


def get_tts() -> PiperTTS:
    """Fresh instance each call — piper is a subprocess, nothing to cache."""
    piper = find_piper()
    voice = find_piper_voice()
    if not piper or not voice:
        raise RuntimeError("Piper TTS not configured (binary or voice model missing).")
    return PiperTTS(piper, voice)


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
    piper = find_piper() is not None and find_piper_voice() is not None
    return {
        "configured": stt or piper,
        "stt": {"provider": "faster-whisper", "available": stt,
                "detail": "" if stt else "pip install faster-whisper"},
        "tts": {"provider": "piper", "available": piper,
                "detail": "" if piper else
                "Put piper.exe in tools/piper/ and a voice .onnx in tools/piper/voices/"},
        "wake_word": {"provider": "openwakeword", "available": wake,
                      "detail": "" if wake else "pip install openwakeword",
                      "phrase": "Athena"},
        "modes": ["push_to_talk", "conversation", "command"],
        "note": "Voice is optional — Athena runs fully without it.",
    }
