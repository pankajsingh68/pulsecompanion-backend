"""Relational Pattern Memory — long-horizon interaction pattern tracking.

Emotional continuity, not surveillance. Tracks baselines, overload frequency,
recovery trends, and trust stability across sessions.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from utils.logger import get_logger

logger = get_logger(__name__)

PATTERN_VERSION = 1
BASELINE_ALPHA = 0.05
MAX_SESSIONS = 30


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


@dataclass(frozen=True)
class RelationalPatternState:
    """Output: long-horizon relational pattern state."""
    stress_baseline: float
    engagement_baseline: float
    openness_baseline: float
    overload_frequency: float
    recovery_trend: float
    trust_stability: float
    pattern_version: int


class RelationalPatternMemory:
    """Tracks long-horizon interaction patterns across sessions."""

    def __init__(self) -> None:
        self._stress_baseline: float = 0.3
        self._engagement_baseline: float = 0.5
        self._openness_baseline: float = 0.5
        self._trust_stability: float = 0.5
        self._overload_history: deque[bool] = deque(maxlen=30)
        self._recovery_history: deque[float] = deque(maxlen=10)
        self._session_count: int = 0
        self._sessions: deque[dict] = deque(maxlen=MAX_SESSIONS)
        self._output: RelationalPatternState | None = None
        self._trust_events: deque[dict] = deque(maxlen=50)

    def update_after_cycle(
        self,
        stress: float,
        engagement: float,
        openness: float,
        overload_detected: bool,
        recovery_state: float,
        overload_severity: float,
    ) -> RelationalPatternState:
        """Update patterns after successful cycle completion.

        Called ONLY after full cycle completes — never mid-pipeline.
        """
        # Slow baseline drift
        self._stress_baseline = (
            BASELINE_ALPHA * stress + (1 - BASELINE_ALPHA) * self._stress_baseline
        )
        self._engagement_baseline = (
            BASELINE_ALPHA * engagement + (1 - BASELINE_ALPHA) * self._engagement_baseline
        )
        self._openness_baseline = (
            BASELINE_ALPHA * openness + (1 - BASELINE_ALPHA) * self._openness_baseline
        )

        # Overload frequency
        self._overload_history.append(overload_detected)
        overload_freq = (
            sum(self._overload_history) / len(self._overload_history)
            if self._overload_history else 0.0
        )

        # Recovery trend
        self._recovery_history.append(recovery_state)
        recovery_trend = 0.0
        if len(self._recovery_history) >= 3:
            first_half = list(self._recovery_history)[:len(self._recovery_history)//2]
            second_half = list(self._recovery_history)[len(self._recovery_history)//2:]
            if first_half and second_half:
                avg_first = sum(first_half) / len(first_half)
                avg_second = sum(second_half) / len(second_half)
                recovery_trend = _clamp(avg_second - avg_first, -1.0, 1.0)

        # Trust stability
        if overload_severity > 0.65:
            self._trust_stability = max(0.0, self._trust_stability - 0.10)
            self._trust_events.append({"type": "drop", "severity": overload_severity})
        else:
            self._trust_stability = min(1.0, self._trust_stability + 0.02)

        self._output = RelationalPatternState(
            stress_baseline=round(self._stress_baseline, 6),
            engagement_baseline=round(self._engagement_baseline, 6),
            openness_baseline=round(self._openness_baseline, 6),
            overload_frequency=round(overload_freq, 6),
            recovery_trend=round(recovery_trend, 6),
            trust_stability=round(_clamp(self._trust_stability), 6),
            pattern_version=PATTERN_VERSION,
        )
        return self._output

    def end_session(self, session_summary: dict) -> None:
        """Record session end. Evicts oldest if > MAX_SESSIONS."""
        self._sessions.append(session_summary)
        self._session_count += 1

    @property
    def session_count(self) -> int:
        return len(self._sessions)

    async def get_pattern_summary(self) -> RelationalPatternState | None:
        return self._output

    async def get_trend_diagnostics(self) -> dict:
        return {
            "baseline_drift_rate": BASELINE_ALPHA,
            "overload_frequency_trend": (
                sum(self._overload_history) / max(len(self._overload_history), 1)
            ),
            "recovery_improvement_rate": (
                list(self._recovery_history)[-1] - list(self._recovery_history)[0]
                if len(self._recovery_history) >= 2 else 0.0
            ),
            "trust_event_log": list(self._trust_events)[-5:],
            "sessions_retained": len(self._sessions),
        }
