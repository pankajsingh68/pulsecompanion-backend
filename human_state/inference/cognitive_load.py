"""Cognitive load inferencer — derived from stress, fatigue, and behavior."""

from __future__ import annotations

from typing import TYPE_CHECKING

from utils.helpers import clamp

if TYPE_CHECKING:
    from human_state.models import SignalScores


class CognitiveLoadInferencer:
    """Infer cognitive load from stress, fatigue, and behavioral signals.

    Cognitive load is partially derived from stress + fatigue
    plus direct behavioral signals.
    """

    def infer(
        self,
        signals: "SignalScores",
        stress: float,
        fatigue: float,
        prior: float = 0.5,
    ) -> float:
        """Compute cognitive load.

        Args:
            signals: Normalized signal scores.
            stress: Already-inferred stress value.
            fatigue: Already-inferred fatigue value.
            prior: Previous cognitive load value.

        Returns:
            Cognitive load score in [0.0, 1.0].
        """
        base = (stress * 0.4) + (fatigue * 0.3)

        if signals.behavior_cognitive_load is not None:
            base = (base * 0.5) + (signals.behavior_cognitive_load * 0.5)

        return clamp(base)
