"""Adaptive Interaction Engine — converts emotional + rhythm state into directives.

Controls response character, not response content. A modulation layer above the LLM.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from emotion.emotional_fusion_engine import UnifiedEmotionalState
from emotion.conversational_rhythm_engine import RhythmState
from utils.logger import get_logger

logger = get_logger(__name__)

DIRECTIVE_VERSION = 1
EMA_ALPHA = 0.3
MAX_DELTA = 0.15


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


@dataclass(frozen=True)
class InteractionDirective:
    """Concrete interaction modulation directive."""
    response_intensity: float
    pacing_modifier: float
    emotional_softness: float
    verbosity_target: float
    interruption_sensitivity: float
    reassurance_level: float
    cognitive_load_protection: float
    allow_proactive_checkin: bool
    adaptation_confidence: float
    directive_version: int


class AdaptiveInteractionEngine:
    """Converts emotional state + rhythm into interaction directives."""

    def __init__(self) -> None:
        self._prev: dict[str, float] = {
            "response_intensity": 0.6,
            "pacing_modifier": 1.0,
            "emotional_softness": 0.5,
            "verbosity_target": 0.7,
            "interruption_sensitivity": 0.6,
            "reassurance_level": 0.3,
            "cognitive_load_protection": 0.3,
            "adaptation_confidence": 0.7,
        }
        self._prev_smoothed: dict[str, float] = dict(self._prev)
        self._allow_proactive: bool = True
        self._output: InteractionDirective | None = None
        self._history: deque[InteractionDirective] = deque(maxlen=100)
        self._diagnostics: deque[dict] = deque(maxlen=100)
        self._rule_triggers: int = 0
        self._conservative_count: int = 0
        self._clamping_events: int = 0

    def process_cycle(
        self, emotional: UnifiedEmotionalState, rhythm: RhythmState
    ) -> InteractionDirective:
        """Produce interaction directive from current state."""
        raw = dict(self._prev)
        self._allow_proactive = True
        conservative = False

        # Low confidence → conservative mode
        if emotional.confidence < 0.4:
            conservative = True
            self._conservative_count += 1

        max_delta = 0.05 if conservative else MAX_DELTA

        # High stress rules
        if emotional.stress > 0.65:
            raw["verbosity_target"] = max(0.3, raw["verbosity_target"] - 0.2)
            raw["emotional_softness"] = min(1.0, raw["emotional_softness"] + 0.2)
            raw["pacing_modifier"] = max(0.6, raw["pacing_modifier"] - 0.15)
            raw["reassurance_level"] = min(1.0, raw["reassurance_level"] + 0.15)
            raw["cognitive_load_protection"] = min(1.0, raw["cognitive_load_protection"] + 0.2)
            self._rule_triggers += 1

        # High cognitive load
        if emotional.cognitive_load > 0.65:
            raw["verbosity_target"] = max(0.25, raw["verbosity_target"] - 0.25)
            raw["interruption_sensitivity"] = max(0.2, raw["interruption_sensitivity"] - 0.2)
            raw["pacing_modifier"] = max(0.5, raw["pacing_modifier"] - 0.2)
            self._rule_triggers += 1

        # Low engagement
        if emotional.engagement < 0.35:
            raw["emotional_softness"] = min(0.8, raw["emotional_softness"] + 0.1)
            self._allow_proactive = False
            raw["response_intensity"] = max(0.3, raw["response_intensity"] - 0.1)
            self._rule_triggers += 1

        # High recovery
        if emotional.recovery_state > 0.7:
            raw["pacing_modifier"] = min(1.0, raw["pacing_modifier"] + 0.05)
            raw["reassurance_level"] = max(0.0, raw["reassurance_level"] - 0.05)
            raw["cognitive_load_protection"] = max(0.0, raw["cognitive_load_protection"] - 0.05)

        # Low emotional openness
        if emotional.emotional_openness < 0.35:
            self._allow_proactive = False
            raw["response_intensity"] = max(0.2, raw["response_intensity"] - 0.15)

        raw["adaptation_confidence"] = emotional.confidence

        # EMA smoothing
        smoothed: dict[str, float] = {}
        for dim in self._prev:
            smoothed[dim] = EMA_ALPHA * raw[dim] + (1 - EMA_ALPHA) * self._prev_smoothed[dim]

        # Rate clamping
        final: dict[str, float] = {}
        for dim in self._prev:
            lo = self._prev[dim] - max_delta
            hi = self._prev[dim] + max_delta
            clamped = _clamp(smoothed[dim], lo, hi)
            if clamped != smoothed[dim]:
                self._clamping_events += 1
            final[dim] = _clamp(clamped)

        self._prev = dict(final)
        self._prev_smoothed = dict(smoothed)

        self._output = InteractionDirective(
            response_intensity=round(final["response_intensity"], 6),
            pacing_modifier=round(final["pacing_modifier"], 6),
            emotional_softness=round(final["emotional_softness"], 6),
            verbosity_target=round(final["verbosity_target"], 6),
            interruption_sensitivity=round(final["interruption_sensitivity"], 6),
            reassurance_level=round(final["reassurance_level"], 6),
            cognitive_load_protection=round(final["cognitive_load_protection"], 6),
            allow_proactive_checkin=self._allow_proactive,
            adaptation_confidence=round(final["adaptation_confidence"], 6),
            directive_version=DIRECTIVE_VERSION,
        )
        self._history.append(self._output)
        return self._output

    async def get_current_directive(self) -> InteractionDirective | None:
        return self._output

    async def get_adaptation_diagnostics(self) -> dict:
        return {
            "rule_triggers": self._rule_triggers,
            "conservative_mode_count": self._conservative_count,
            "clamping_events": self._clamping_events,
        }
