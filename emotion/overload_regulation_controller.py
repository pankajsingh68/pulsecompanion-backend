"""Overload Regulation Controller — circuit breaker for interaction layer.

Detects emotional/cognitive overwhelm and suppresses system behavior
that would make it worse.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from emotion.emotional_fusion_engine import UnifiedEmotionalState
from emotion.conversational_rhythm_engine import RhythmState
from utils.logger import get_logger

logger = get_logger(__name__)

REGULATION_VERSION = 1
EMA_ALPHA = 0.2
MAX_SEVERITY_DELTA = 0.10


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


@dataclass(frozen=True)
class RegulationDecision:
    """Output: overload regulation decision."""
    overload_detected: bool
    overload_severity: float
    stabilization_required: bool
    reduce_response_complexity: bool
    suppress_proactive_behavior: bool
    recommend_pause: bool
    recovery_mode_active: bool
    regulation_confidence: float
    regulation_version: int


class OverloadRegulationController:
    """Detects overload and suppresses harmful system behavior."""

    def __init__(self) -> None:
        self._prev_severity: float = 0.2
        self._overload_active: bool = False
        self._calm_streak: int = 0
        self._overload_duration: int = 0
        self._stress_decline_streak: int = 0
        self._recovery_active: bool = False
        self._recovery_stable_count: int = 0
        self._prev_stress: float = 0.3
        self._output: RegulationDecision | None = None
        self._history: deque[RegulationDecision] = deque(maxlen=100)
        self._severity_history: deque[float] = deque(maxlen=100)
        self._diagnostics: deque[dict] = deque(maxlen=100)
        self._suppression_count: int = 0

    def process_cycle(
        self, emotional: UnifiedEmotionalState, rhythm: RhythmState
    ) -> RegulationDecision:
        """Evaluate overload and produce regulation decision."""
        # Compute overload score
        score = (
            0.35 * emotional.stress
            + 0.25 * emotional.cognitive_load
            + 0.20 * rhythm.interruption_load
            + 0.20 * (1.0 - rhythm.pacing_stability)
        )
        score = _clamp(score)

        # EMA smooth severity
        smoothed_severity = EMA_ALPHA * score + (1 - EMA_ALPHA) * self._prev_severity
        # Rate clamp
        lo = self._prev_severity - MAX_SEVERITY_DELTA
        hi = self._prev_severity + MAX_SEVERITY_DELTA
        severity = _clamp(smoothed_severity, lo, hi)
        severity = _clamp(severity)
        self._prev_severity = severity
        self._severity_history.append(severity)

        # Hysteresis for overload detection
        if not self._overload_active:
            if score > 0.55:
                self._overload_active = True
                self._calm_streak = 0
        else:
            if score < 0.45:
                self._calm_streak += 1
            else:
                self._calm_streak = 0
            if self._calm_streak >= 3:
                self._overload_active = False
                self._overload_duration = 0

        if self._overload_active:
            self._overload_duration += 1

        # Stress tracking for recovery
        if emotional.stress < self._prev_stress:
            self._stress_decline_streak += 1
        else:
            self._stress_decline_streak = 0
        self._prev_stress = emotional.stress

        # Recovery mode
        if (self._overload_active and self._overload_duration >= 2
                and self._stress_decline_streak >= 3
                and rhythm.pacing_stability > 0.5):
            self._recovery_active = True
            self._recovery_stable_count = 0

        if self._recovery_active:
            if not self._overload_active and rhythm.pacing_stability > 0.6:
                self._recovery_stable_count += 1
            if self._recovery_stable_count >= 5:
                self._recovery_active = False

        # Decisions
        stabilization = score > 0.70
        suppress = score > 0.80
        reduce_complexity = score > 0.80
        recommend_pause = score > 0.90

        if suppress:
            self._suppression_count += 1

        self._output = RegulationDecision(
            overload_detected=self._overload_active,
            overload_severity=round(severity, 6),
            stabilization_required=stabilization,
            reduce_response_complexity=reduce_complexity,
            suppress_proactive_behavior=suppress,
            recommend_pause=recommend_pause,
            recovery_mode_active=self._recovery_active,
            regulation_confidence=round(emotional.confidence, 6),
            regulation_version=REGULATION_VERSION,
        )
        self._history.append(self._output)
        return self._output

    async def get_regulation_state(self) -> RegulationDecision | None:
        return self._output

    async def get_overload_metrics(self) -> dict:
        return {
            "severity_trend": list(self._severity_history)[-10:],
            "hysteresis_calm_streak": self._calm_streak,
            "recovery_mode_duration": self._recovery_stable_count,
            "suppression_count": self._suppression_count,
        }
