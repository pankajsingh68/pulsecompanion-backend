"""Fatigue inferencer — combines biometric, text, and behavioral signals."""

from __future__ import annotations

from typing import TYPE_CHECKING

from utils.helpers import clamp

if TYPE_CHECKING:
    from human_state.models import SignalScores


class FatigueInferencer:
    """Infer fatigue level from available signal scores."""

    def infer(self, signals: "SignalScores", prior: float = 0.2) -> float:
        """Compute fatigue from weighted signal combination.

        Args:
            signals: Normalized signal scores from all extractors.
            prior: Previous fatigue value for temporal context.

        Returns:
            Fatigue score in [0.0, 1.0].
        """
        scores: list[float] = []
        weights: list[float] = []

        if signals.bio_fatigue is not None:
            scores.append(signals.bio_fatigue)
            weights.append(0.5)

        if signals.text_fatigue is not None:
            scores.append(signals.text_fatigue)
            weights.append(0.35)

        if signals.behavior_cognitive_load is not None:
            # Behavior is a weak fatigue proxy
            scores.append(signals.behavior_cognitive_load * 0.7)
            weights.append(0.15)

        if not scores:
            return prior

        return clamp(sum(s * w for s, w in zip(scores, weights)) / sum(weights))
