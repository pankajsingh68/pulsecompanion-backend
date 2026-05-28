"""Multimodal fusion — combines all signal scores into a unified RichHumanState."""

from __future__ import annotations

from datetime import datetime, timezone

from utils.helpers import clamp
from human_state.models import RichHumanState, SignalScores
from human_state.inference.stress import StressInferencer
from human_state.inference.fatigue import FatigueInferencer
from human_state.inference.cognitive_load import CognitiveLoadInferencer
from human_state.inference.engagement import EngagementInferencer
from human_state.inference.stability import EmotionalStabilityInferencer


class MultimodalFusion:
    """Combines all signal scores and inference outputs into a single RichHumanState."""

    def __init__(self) -> None:
        self.stress_inf = StressInferencer()
        self.fatigue_inf = FatigueInferencer()
        self.load_inf = CognitiveLoadInferencer()
        self.engagement_inf = EngagementInferencer()
        self.stability_inf = EmotionalStabilityInferencer()

    def fuse(
        self,
        signals: SignalScores,
        prior_state: RichHumanState | None = None,
        session_context: dict | None = None,
    ) -> RichHumanState:
        """Single entry point: takes all signals, returns RichHumanState.

        Args:
            signals: Normalized signal scores from all extractors.
            prior_state: Last known state for temporal smoothing context.
            session_context: Optional session-level context.

        Returns:
            A fully populated RichHumanState.
        """
        prior = prior_state or RichHumanState(
            stress=0.2,
            focus=0.5,
            fatigue=0.2,
            confidence=0.8,
            ux_mode="normal",
            timestamp=datetime.now(timezone.utc),
        )

        # Run all inferencers
        stress = self.stress_inf.infer(signals, prior.stress)
        fatigue = self.fatigue_inf.infer(signals, prior.fatigue)
        cognitive_load = self.load_inf.infer(
            signals, stress, fatigue, prior.cognitive_load
        )
        engagement = self.engagement_inf.infer(
            signals, cognitive_load, prior.engagement
        )
        stability = self.stability_inf.infer(signals, stress, prior.emotional_stability)

        # Derived dimensions
        focus = (
            signals.text_focus if signals.text_focus is not None else prior.focus
        )
        confidence = clamp(1.0 - (stress * 0.4 + fatigue * 0.3))
        receptiveness = clamp(
            engagement * 0.6 + stability * 0.4 - cognitive_load * 0.3
        )
        social_energy = clamp(
            engagement * 0.5 + stability * 0.3 - fatigue * 0.4
        )
        recovery_need = clamp(
            (stress + fatigue) / 2 + cognitive_load * 0.3
        )

        # Determine trend vs prior
        trend = self._compute_trend(stress, fatigue, prior)

        # Inference confidence: more sources = more confident
        inference_confidence = min(
            len(signals.contributing_sources) * 0.25 + 0.25, 1.0
        )

        # UX mode routing
        from human_state.orchestration.ux_router import route_ux_mode

        ux_mode = route_ux_mode(stress, focus, fatigue, cognitive_load, recovery_need)

        return RichHumanState(
            stress=stress,
            focus=focus,
            fatigue=fatigue,
            confidence=confidence,
            ux_mode=ux_mode,
            timestamp=datetime.now(timezone.utc),
            cognitive_load=cognitive_load,
            engagement=engagement,
            emotional_stability=stability,
            social_energy=social_energy,
            receptiveness=receptiveness,
            recovery_need=recovery_need,
            signal_sources=signals.contributing_sources,
            inference_confidence=inference_confidence,
            trend=trend,
        )

    def _compute_trend(
        self, stress: float, fatigue: float, prior: RichHumanState
    ) -> str:
        """Determine state trend relative to prior state."""
        stress_delta = stress - prior.stress
        fatigue_delta = fatigue - prior.fatigue

        if stress_delta > 0.15 or fatigue_delta > 0.15:
            return "deteriorating"
        if stress_delta < -0.15 and fatigue_delta < -0.1:
            return "improving"
        if stress_delta > 0.08:
            return "rising_stress"
        if stress_delta < -0.08:
            return "recovering"
        return "stable"
