"""SenseVoice adapter seam — protocol + stub + feature-flag loader.

When SenseVoice is not installed, falls back to heuristic extractor silently.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class SenseVoiceOutput:
    """Output from SenseVoice prosody extraction."""
    pacing_pressure: float
    hesitation_index: float
    speech_instability: float
    urgency_level: float
    strain_index: float
    silence_comfort: float
    extraction_confidence: float
    model_version: str


class SenseVoiceBackend(Protocol):
    """Protocol SenseVoice must satisfy when integrated."""
    async def extract_prosody(self, audio_bytes: bytes, sample_rate: int) -> SenseVoiceOutput: ...


class SenseVoiceStub:
    """Stub implementation — returns neutral values."""

    async def extract_prosody(self, audio_bytes: bytes, sample_rate: int) -> SenseVoiceOutput:
        return SenseVoiceOutput(
            pacing_pressure=0.3, hesitation_index=0.3,
            speech_instability=0.2, urgency_level=0.2,
            strain_index=0.2, silence_comfort=0.5,
            extraction_confidence=0.1, model_version="stub",
        )


def _sensevoice_importable() -> bool:
    """Check if SenseVoice package is available."""
    try:
        import importlib
        importlib.import_module("sensevoice")
        return True
    except ImportError:
        return False
