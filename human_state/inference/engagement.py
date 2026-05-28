"""Engagement inferencer — active participation level."""

from __future__ import annotations

from typing import TYPE_CHECKING

from utils.helpers import clamp

if TYPE_CHECKING:
    from human_state.models import SignalScores


class EngagementInferencer:
    """Infer engagement level from text and behavioral signals."""

    def infer(
        self,
        signals: "SignalScores",
        cognitive_load: float,
        prior: float = 0.5,
    ) -> float:
        """Compute engagement.

        Args:
            signals: Normalized signal scores.
            cognitive_load: Already-inferred cognitive load (high load reduces engagement).
            prior: Previous engagement value.

        Returns:
            Engagement score in [0.0, 1.0].
        """
        scores: list[float] = []
        weights: list[float] = []

        if signals.text_engagement is not None:
            scores.append(signals.text_engagement)
            weights.append(0.5)

        if signals.behavior_engagement is not None:
            scores.append(signals.behavior_engagement)
            weights.append(0.4)

        # High cognitive load slightly reduces engagement
        overload_penalty = max(0, cognitive_load - 0.7) * 0.5

        if scores:
            base = sum(s * w for s, w in zip(scores, weights)) / sum(weights)
        else:
            base = prior

        return clamp(base - overload_penalty)
