"""Orchestration explainability — human-readable reasoning for decisions."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from orchestration.models import UXStrategy


class OrchestrationExplainer:
    """Generates human-readable reasoning for every orchestration decision."""

    def build_reasoning(
        self, state: dict, strategy: "UXStrategy", rule_outputs: dict
    ) -> list[str]:
        """Build list of plain-English reasoning strings.

        Args:
            state: The human state dict.
            strategy: The computed UXStrategy.
            rule_outputs: Dict of reason strings from each rule module.

        Returns:
            List of reasoning strings.
        """
        reasons: list[str] = []

        # Tone reasoning
        tone_reason = rule_outputs.get("tone_reason", "")
        if tone_reason:
            reasons.append(f"Tone set to {strategy.response_tone.value}: {tone_reason}")

        # Notification reasoning
        notif_reason = rule_outputs.get("notif_reason", "")
        if strategy.suppress_notifications and notif_reason:
            reasons.append(f"Notifications suppressed: {notif_reason}")

        # Cognitive support reasoning
        cog_reason = rule_outputs.get("cog_reason", "")
        if strategy.cognitive_load_reduction or strategy.suggest_break:
            parts = []
            if strategy.cognitive_load_reduction:
                parts.append("cognitive load reduction active")
            if strategy.suggest_break:
                parts.append("break suggested")
            reasons.append(f"{', '.join(parts)}: {cog_reason}")

        # Emotional support reasoning
        support_reason = rule_outputs.get("support_reason", "")
        if strategy.emotional_support_level > 0.5 and support_reason:
            reasons.append(f"Emotional support elevated: {support_reason}")

        # Verbosity reasoning
        stress = state.get("stress", 0)
        if strategy.verbosity_level.value in ("minimal", "short"):
            reasons.append(
                f"Verbosity reduced to {strategy.verbosity_level.value}: "
                f"stress at {stress:.2f}"
            )

        # Include any existing reasoning (from temporal adaptation)
        reasons.extend(strategy.reasoning)

        return reasons

    def build_contributing_factors(self, state: dict) -> dict:
        """Return subset of state values that are decision-relevant."""
        return {
            "stress": round(state.get("stress", 0), 3),
            "fatigue": round(state.get("fatigue", 0), 3),
            "focus": round(state.get("focus", 0), 3),
            "cognitive_load": round(state.get("cognitive_load", 0), 3),
            "recovery_need": round(state.get("recovery_need", 0), 3),
            "engagement": round(state.get("engagement", 0), 3),
            "emotional_stability": round(state.get("emotional_stability", 0), 3),
            "inference_confidence": round(state.get("inference_confidence", 0), 3),
        }
