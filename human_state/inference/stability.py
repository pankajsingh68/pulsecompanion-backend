"""Emotional stability inferencer — resistance to state swings."""

from __future__ import annotations

from typing import TYPE_CHECKING

from utils.helpers import clamp

if TYPE_CHECKING:
    from human_state.models import SignalScores


class EmotionalStabilityInferencer:
    """Infer emotional stability from stress and HRV signals.

    Stability = inverse of stress volatility + HRV signal.
    High HRV = high vagal tone = more stable.
    """

    def infer(
        self,
        signals: "SignalScores",
        stress: float,
        prior: float = 0.7,
    ) -> float:
        """Compute emotional stability.

        Args:
            signals: Normalized signal scores.
            stress: Already-inferred stress value.
            prior: Previous stability value.

        Returns:
            Emotional stability score in [0.0, 1.0].
        """
        base = 1.0 - (stress * 0.6)

        if signals.bio_stability is not None:
            base = (base * 0.5) + (signals.bio_stability * 0.5)

        return clamp(base)
