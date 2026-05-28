"""Kokoro TTS Backend — local TTS via Kokoro ONNX.

No network call. Lazy-loads model on first use.
Falls back to silence (empty bytes) if kokoro not installed.
"""

from __future__ import annotations

import asyncio
from functools import partial

from utils.logger import get_logger

logger = get_logger(__name__)


def _kokoro_available() -> bool:
    """Check if kokoro-onnx is installed."""
    try:
        import importlib
        importlib.import_module("kokoro_onnx")
        return True
    except ImportError:
        return False


class KokoroTTSBackend:
    """Local TTS via Kokoro ONNX. No network call.

    If kokoro not installed: returns empty bytes (silence).
    Runs synthesis in thread pool executor (CPU-bound).
    """

    def __init__(self, voice: str = "af_heart", lang: str = "en-us") -> None:
        self._voice = voice
        self._lang = lang
        self._model = None
        self._available = _kokoro_available()
        self._initialized = False

        if not self._available:
            logger.warning("kokoro_tts_not_installed", fallback="silence")

    @property
    def name(self) -> str:
        return "kokoro"

    @property
    def available(self) -> bool:
        return self._available

    def _lazy_init(self) -> bool:
        """Lazy-load Kokoro model on first call."""
        if self._initialized:
            return self._model is not None

        self._initialized = True
        if not self._available:
            return False

        try:
            import os
            from kokoro_onnx import Kokoro

            # Resolve model file paths relative to backend/ directory
            _BASE = os.path.dirname(os.path.abspath(__file__))
            _MODEL_DIR = os.path.join(_BASE, "..", "..", "models", "kokoro")
            _ONNX_PATH = os.path.join(_MODEL_DIR, "kokoro-v1.0.onnx")
            _VOICES_PATH = os.path.join(_MODEL_DIR, "voices-v1.0.bin")

            logger.info(
                "kokoro_loading",
                onnx_path=os.path.abspath(_ONNX_PATH),
                voices_path=os.path.abspath(_VOICES_PATH),
            )

            self._model = Kokoro(_ONNX_PATH, _VOICES_PATH)
            logger.info("kokoro_tts_initialized", voice=self._voice)
            return True
        except Exception as e:
            logger.warning("kokoro_init_failed", error=str(e))
            self._model = None
            return False

    async def synthesize_chunk(
        self, text: str, rate: float, softness: float
    ) -> bytes:
        """Synthesize text to WAV bytes.

        rate: 0.5–1.5 maps to Kokoro speed parameter.
        softness: ignored (no direct Kokoro param).
        On any error: returns b"" (never raises).
        """
        if not text or not text.strip():
            return b""

        if not self._lazy_init():
            return b""  # fallback to silence

        try:
            loop = asyncio.get_running_loop()
            # Run CPU-bound synthesis in thread pool
            audio_bytes = await loop.run_in_executor(
                None,
                partial(self._synthesize_sync, text, rate),
            )
            return audio_bytes
        except Exception as e:
            logger.warning("kokoro_synthesis_failed", error=str(e))
            return b""

    def _synthesize_sync(self, text: str, rate: float) -> bytes:
        """Synchronous synthesis (runs in thread pool)."""
        try:
            # Kokoro API: generate(text, speed=rate)
            samples, sample_rate = self._model.create(
                text, voice=self._voice, speed=max(0.5, min(1.5, rate))
            )
            # Convert to WAV bytes
            import io
            import wave
            import struct

            buf = io.BytesIO()
            with wave.open(buf, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                # Convert float samples to int16
                int_samples = [int(max(-1, min(1, s)) * 32767) for s in samples]
                wf.writeframes(struct.pack(f"<{len(int_samples)}h", *int_samples))

            return buf.getvalue()
        except Exception as e:
            logger.warning("kokoro_sync_failed", error=str(e))
            return b""
