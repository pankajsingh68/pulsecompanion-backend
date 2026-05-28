"""Stress inferencer — weighted combination of stress signals."""

from __future__ import annotations

from typing import TYPE_CHECKING

from utils.helpers import clamp

if TYPE_CHECKING:
    from human_state.models import SignalScores


class StressInferencer:
    """Infer stress level from available signal scores.

    Weights biometric signals higher than text (biometrics are more objective).
    """

    def infer(self, signals: "SignalScores", prior: float = 0.0) -> float:
        """Compute stress from weighted signal combination.

        Args:
            signals: Normalized signal scores from all extractors.
            prior: Previous stress value for temporal context.

        Returns:
            Stress score in [0.0, 1.0].
        """
        scores: list[float] = []
        weights: list[float] = []

        if signals.bio_stress is not None:
            scores.append(signals.bio_stress)
            weights.append(0.6)  # biometrics weighted higher

        if signals.text_stress is not None:
            scores.append(signals.text_stress)
            weights.append(0.4)

        if not scores:
            return prior  # no signals → keep prior

        raw = sum(s * w for s, w in zip(scores, weights)) / sum(weights)
        return clamp(raw)
