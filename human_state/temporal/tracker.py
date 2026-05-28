"""Temporal state tracking with exponential moving average smoothing."""

from __future__ import annotations

from human_state.models import RichHumanState
from utils.helpers import clamp


class TemporalStateTracker:
    """Prevents single-message spikes from causing extreme state changes.

    Uses EMA: new_value = alpha * raw + (1 - alpha) * previous
    alpha = 0.35 means 65% weight on history (stable but responsive).
    """

    ALPHA = 0.35

    def __init__(self) -> None:
        self._history: list[RichHumanState] = []
        self._smoothed: RichHumanState | None = None

    def update(self, raw_state: RichHumanState) -> RichHumanState:
        """Apply EMA smoothing to raw inferred state.

        Args:
            raw_state: The unsmoothed state from fusion.

        Returns:
            Smoothed RichHumanState.
        """
        if self._smoothed is None:
            # First state — no smoothing needed
            self._smoothed = raw_state
            self._history.append(raw_state)
            return raw_state

        # Apply EMA to numeric dimensions
        alpha = self.ALPHA
        prev = self._smoothed

        smoothed = raw_state.model_copy(update={
            "stress": self._ema(raw_state.stress, prev.stress, alpha),
            "fatigue": self._ema(raw_state.fatigue, prev.fatigue, alpha),
            "focus": self._ema(raw_state.focus, prev.focus, alpha),
            "cognitive_load": self._ema(
                raw_state.cognitive_load, prev.cognitive_load, alpha
            ),
            "engagement": self._ema(
                raw_state.engagement, prev.engagement, alpha
            ),
            "emotional_stability": self._ema(
                raw_state.emotional_stability, prev.emotional_stability, alpha
            ),
            "recovery_need": self._ema(
                raw_state.recovery_need, prev.recovery_need, alpha
            ),
            "confidence": self._ema(
                raw_state.confidence, prev.confidence, alpha
            ),
        })

        self._smoothed = smoothed
        self._history.append(smoothed)

        # Keep only last 50 states (session memory)
        if len(self._history) > 50:
            self._history.pop(0)

        return smoothed

    def _ema(self, new: float, prev: float, alpha: float) -> float:
        """Exponential moving average."""
        return clamp(alpha * new + (1 - alpha) * prev)

    def get_trend_window(self, n: int = 5) -> list[RichHumanState]:
        """Return the last N states for trend analysis."""
        return self._history[-n:]

    def get_session_averages(self) -> dict:
        """Compute average values across the session history."""
        if not self._history:
            return {}

        fields = [
            "stress", "fatigue", "focus", "cognitive_load", "engagement",
        ]
        return {
            f: round(
                sum(getattr(s, f) for s in self._history) / len(self._history),
                3,
            )
            for f in fields
        }
