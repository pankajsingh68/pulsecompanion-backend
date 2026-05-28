"""Response Modulator — translates InteractionDirective into voice parameters.

Controls how the response sounds. Does NOT touch content.
EMA alpha=0.3, rate-clamp ±0.10/cycle.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from emotion.adaptive_interaction_engine import InteractionDirective
from utils.logger import get_logger

logger = get_logger(__name__)

MODULATION_VERSION = 1
EMA_ALPHA = 0.3
MAX_DELTA = 0.10


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


@dataclass(frozen=True)
class VoiceModulation:
    speaking_rate: float
    pause_before_response: float
    inter_sentence_pause: float
    softness_level: float
    response_timing_mode: str
    allow_mid_response_pause: bool
    max_response_sentences: int
    modulation_version: int


class ResponseModulator:
    """Translates InteractionDirective into VoiceModulation parameters."""

    def __init__(self) -> None:
        self._prev: dict[str, float] = {
            "speaking_rate": 1.0,
            "pause_before_response": 0.3,
            "inter_sentence_pause": 0.3,
            "softness_level": 0.4,
        }
        self._prev_smoothed: dict[str, float] = dict(self._prev)
        self._history: deque[VoiceModulation] = deque(maxlen=50)
        self._output: VoiceModulation | None = None

    def modulate(self, directive: InteractionDirective) -> VoiceModulation:
        """Produce VoiceModulation from InteractionDirective."""
        raw = dict(self._prev)
        timing_mode = "immediate"
        max_sentences = 4
        allow_mid_pause = False

        # Mapping rules
        if directive.pacing_modifier < 0.7:
            raw["speaking_rate"] = 0.75
            raw["inter_sentence_pause"] = self._prev["inter_sentence_pause"] + 0.3

        if directive.emotional_softness > 0.7:
            raw["softness_level"] = max(0.7, directive.emotional_softness)
            timing_mode = "grounded"

        if directive.cognitive_load_protection > 0.7:
            max_sentences = 2
            raw["pause_before_response"] = self._prev["pause_before_response"] + 0.5
            allow_mid_pause = True

        if directive.reassurance_level > 0.6:
            raw["pause_before_response"] = self._prev["pause_before_response"] + 0.3
            if timing_mode == "immediate":
                timing_mode = "considered"

        if directive.verbosity_target < 0.35:
            max_sentences = 1

        # EMA smoothing
        smoothed: dict[str, float] = {}
        for dim in self._prev:
            smoothed[dim] = EMA_ALPHA * raw[dim] + (1 - EMA_ALPHA) * self._prev_smoothed[dim]

        # Rate clamping
        final: dict[str, float] = {}
        for dim in self._prev:
            lo = self._prev[dim] - MAX_DELTA
            hi = self._prev[dim] + MAX_DELTA
            final[dim] = _clamp(smoothed[dim], lo, hi)

        # Bound outputs
        final["speaking_rate"] = _clamp(final["speaking_rate"], 0.5, 1.5)
        final["pause_before_response"] = _clamp(final["pause_before_response"], 0.0, 2.0)
        final["inter_sentence_pause"] = _clamp(final["inter_sentence_pause"], 0.0, 1.0)
        final["softness_level"] = _clamp(final["softness_level"], 0.0, 1.0)

        self._prev = dict(final)
        self._prev_smoothed = dict(smoothed)

        self._output = VoiceModulation(
            speaking_rate=round(final["speaking_rate"], 4),
            pause_before_response=round(final["pause_before_response"], 4),
            inter_sentence_pause=round(final["inter_sentence_pause"], 4),
            softness_level=round(final["softness_level"], 4),
            response_timing_mode=timing_mode,
            allow_mid_response_pause=allow_mid_pause,
            max_response_sentences=max_sentences,
            modulation_version=MODULATION_VERSION,
        )
        self._history.append(self._output)
        return self._output
