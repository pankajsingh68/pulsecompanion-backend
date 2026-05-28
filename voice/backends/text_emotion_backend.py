"""Text emotion backend — DistillRoBERTa adapter seam.

Protocol + stub. When not injected, pipeline skips text emotion silently.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class TextEmotionOutput:
    """Output from text emotion analysis."""
    stress: float
    engagement: float
    emotional_openness: float
    cognitive_load: float
    confidence: float
    model_version: str


class TextEmotionBackend(Protocol):
    """Protocol for text emotion backends (DistillRoBERTa, etc.)."""
    async def analyze(self, text: str) -> TextEmotionOutput: ...


class TextEmotionStub:
    """Stub — returns neutral values. Replace with DistillRoBERTa."""

    async def analyze(self, text: str) -> TextEmotionOutput:
        return TextEmotionOutput(
            stress=0.3, engagement=0.5, emotional_openness=0.5,
            cognitive_load=0.3, confidence=0.2, model_version="stub",
        )
