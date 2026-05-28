"""Composite orchestration confidence engine."""

import statistics

from confidence.confidence_models import ModalityConfidence, OrchestrationConfidence
from utils.helpers import clamp


class OrchestrationConfidenceEngine:
    """Composes final orchestration confidence from all sources.

    Low confidence → conservative strategy (less adaptation, smaller jumps).
    """

    def compute(
        self,
        modality_conf: ModalityConfidence,
        state_history: list[dict],
        rule_outputs: dict | None = None,
    ) -> OrchestrationConfidence:
        """Compute composite orchestration confidence.

        Args:
            modality_conf: Per-signal confidence.
            state_history: Recent state dicts for stability calculation.
            rule_outputs: Rule decision outputs for agreement calculation.

        Returns:
            OrchestrationConfidence with composite score.
        """
        # Policy agreement: fraction of rules that produced non-default output
        policy_agreement = self._compute_policy_agreement(rule_outputs or {})

        # State stability: inverse of stress stddev over recent history
        state_stability = self._compute_state_stability(state_history)

        # Composite weighted score
        composite = clamp(
            modality_conf.overall * 0.5
            + policy_agreement * 0.3
            + state_stability * 0.2
        )

        reasoning: list[str] = []
        if modality_conf.overall < 0.5:
            reasoning.append(
                f"low sensor confidence ({modality_conf.overall:.2f})"
            )
        if state_stability < 0.5:
            reasoning.append(
                f"unstable state history (stability={state_stability:.2f})"
            )

        return OrchestrationConfidence(
            modality=modality_conf,
            policy_agreement=policy_agreement,
            state_stability=state_stability,
            composite=composite,
            is_high_confidence=composite > 0.65,
            reasoning=reasoning,
        )

    def _compute_policy_agreement(self, rule_outputs: dict) -> float:
        """Estimate how much rules agree (1.0 = all agree)."""
        if not rule_outputs:
            return 0.8  # default: assume moderate agreement
        # Count non-empty reasons as active rules
        active = sum(1 for v in rule_outputs.values() if v)
        return clamp(active / max(len(rule_outputs), 1))

    def _compute_state_stability(self, state_history: list[dict]) -> float:
        """Compute stability from stress variance over recent history."""
        if len(state_history) < 2:
            return 0.8  # not enough data, assume stable

        stresses = [s.get("stress", 0.5) for s in state_history[-5:]]
        if len(stresses) < 2:
            return 0.8

        stddev = statistics.stdev(stresses)
        # Low stddev = high stability
        return clamp(1.0 - stddev * 3.0)
