"""Adaptive stabilizer — runtime-active instability prevention.

Runtime actively PREVENTS instability rather than just detecting it.
Implements: orchestration hysteresis, emotional continuity damping,
confidence spike prevention, recovery stabilization.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from utils.helpers import clamp
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class StabilityIntervention:
    """Record of a stability intervention applied by the runtime."""
    intervention_type: str
    reason: str
    original_value: Any = None
    corrected_value: Any = None
    lineage_id: UUID | None = None
    timestamp: float = field(default_factory=time.monotonic)


@dataclass
class StabilityMetrics:
    """Aggregate stability metrics."""
    oscillation_preventions: int = 0
    confidence_clamps: int = 0
    continuity_corrections: int = 0
    degraded_recovery_interventions: int = 0
    total_interventions: int = 0


class OrchestrationHysteresis:
    """Prevents rapid UX mode flipping.

    Minimum decision interval + confidence hysteresis threshold.
    """

    MIN_DECISION_INTERVAL_MS = 3000.0
    CONFIDENCE_HYSTERESIS = 0.15  # must exceed by this much to change

    def __init__(self) -> None:
        self._last_mode: dict[str, str] = {}
        self._last_change_time: dict[str, float] = {}
        self._last_confidence: dict[str, float] = {}

    def should_allow_change(
        self, session_id: str, proposed_mode: str, confidence: float
    ) -> tuple[bool, str]:
        """Check if a mode change should be allowed.

        Returns (allowed, reason).
        """
        current_mode = self._last_mode.get(session_id, "normal")
        last_time = self._last_change_time.get(session_id, 0)
        last_conf = self._last_confidence.get(session_id, 0.5)

        # Same mode — always allow
        if proposed_mode == current_mode:
            return True, ""

        # Check minimum interval
        elapsed_ms = (time.monotonic() - last_time) * 1000
        if elapsed_ms < self.MIN_DECISION_INTERVAL_MS:
            return False, f"cooldown: {elapsed_ms:.0f}ms < {self.MIN_DECISION_INTERVAL_MS}ms"

        # Check confidence hysteresis
        if confidence < last_conf + self.CONFIDENCE_HYSTERESIS:
            return False, f"confidence_hysteresis: {confidence:.2f} < {last_conf:.2f} + {self.CONFIDENCE_HYSTERESIS}"

        return True, ""

    def record_change(self, session_id: str, mode: str, confidence: float) -> None:
        """Record that a mode change was committed."""
        self._last_mode[session_id] = mode
        self._last_change_time[session_id] = time.monotonic()
        self._last_confidence[session_id] = confidence


class EmotionalContinuityDamper:
    """Prevents impossible emotional jumps between consecutive states.

    Bounded delta between consecutive states with trajectory smoothing.
    """

    MAX_STRESS_DELTA = 0.35
    MAX_FATIGUE_DELTA = 0.30
    MAX_FOCUS_DELTA = 0.40

    def __init__(self) -> None:
        self._last_state: dict[str, dict] = {}

    def apply(
        self, session_id: str, state: dict, lineage_id: UUID | None = None
    ) -> tuple[dict, StabilityIntervention | None]:
        """Apply continuity damping to a state.

        Returns (damped_state, intervention_or_None).
        """
        prev = self._last_state.get(session_id)
        if prev is None:
            self._last_state[session_id] = dict(state)
            return state, None

        corrected = dict(state)
        intervention = None

        # Clamp stress delta
        stress_delta = state.get("stress", 0) - prev.get("stress", 0)
        if abs(stress_delta) > self.MAX_STRESS_DELTA:
            direction = 1 if stress_delta > 0 else -1
            corrected["stress"] = clamp(
                prev.get("stress", 0) + direction * self.MAX_STRESS_DELTA
            )
            intervention = StabilityIntervention(
                intervention_type="continuity_damping",
                reason=f"stress_delta {stress_delta:.2f} > max {self.MAX_STRESS_DELTA}",
                original_value=state.get("stress"),
                corrected_value=corrected["stress"],
                lineage_id=lineage_id,
            )

        # Clamp fatigue delta
        fatigue_delta = state.get("fatigue", 0) - prev.get("fatigue", 0)
        if abs(fatigue_delta) > self.MAX_FATIGUE_DELTA:
            direction = 1 if fatigue_delta > 0 else -1
            corrected["fatigue"] = clamp(
                prev.get("fatigue", 0) + direction * self.MAX_FATIGUE_DELTA
            )
            if intervention is None:
                intervention = StabilityIntervention(
                    intervention_type="continuity_damping",
                    reason=f"fatigue_delta {fatigue_delta:.2f} > max {self.MAX_FATIGUE_DELTA}",
                    original_value=state.get("fatigue"),
                    corrected_value=corrected["fatigue"],
                    lineage_id=lineage_id,
                )

        self._last_state[session_id] = corrected
        return corrected, intervention


class ConfidenceSpikePreventor:
    """High confidence requires corroboration.

    Confidence escalation only after N corroborating signals.
    Rapid confidence jumps are clamped.
    """

    MAX_CONFIDENCE_JUMP = 0.25
    MIN_CORROBORATING_SIGNALS = 2
    DEGRADED_CONFIDENCE_CEILING = 0.6

    def __init__(self) -> None:
        self._last_confidence: dict[str, float] = {}
        self._signal_counts: dict[str, int] = {}

    def apply(
        self, session_id: str, confidence: float,
        signal_count: int, is_degraded: bool,
        lineage_id: UUID | None = None,
    ) -> tuple[float, StabilityIntervention | None]:
        """Apply confidence spike prevention.

        Returns (clamped_confidence, intervention_or_None).
        """
        prev = self._last_confidence.get(session_id, 0.5)
        intervention = None

        # Degraded mode ceiling
        if is_degraded and confidence > self.DEGRADED_CONFIDENCE_CEILING:
            clamped = self.DEGRADED_CONFIDENCE_CEILING
            intervention = StabilityIntervention(
                intervention_type="confidence_clamp",
                reason=f"degraded_ceiling: {confidence:.2f} > {self.DEGRADED_CONFIDENCE_CEILING}",
                original_value=confidence,
                corrected_value=clamped,
                lineage_id=lineage_id,
            )
            self._last_confidence[session_id] = clamped
            return clamped, intervention

        # Spike prevention
        delta = confidence - prev
        if delta > self.MAX_CONFIDENCE_JUMP:
            if signal_count < self.MIN_CORROBORATING_SIGNALS:
                clamped = prev + self.MAX_CONFIDENCE_JUMP
                intervention = StabilityIntervention(
                    intervention_type="confidence_clamp",
                    reason=f"spike: delta={delta:.2f}, signals={signal_count} < {self.MIN_CORROBORATING_SIGNALS}",
                    original_value=confidence,
                    corrected_value=clamped,
                    lineage_id=lineage_id,
                )
                self._last_confidence[session_id] = clamped
                return clamped, intervention

        self._last_confidence[session_id] = confidence
        return confidence, None


class RecoveryStabilizer:
    """After degraded mode: gradual recovery ramp.

    Prevents immediate orchestration escalation.
    Preserves last-known-good state during instability.
    """

    RECOVERY_RAMP_STEPS = 3
    RECOVERY_RAMP_FACTOR = 0.33  # 33% per step toward full confidence

    def __init__(self) -> None:
        self._recovery_step: dict[str, int] = {}
        self._in_recovery: dict[str, bool] = {}

    def enter_recovery(self, session_id: str) -> None:
        """Mark session as entering recovery from degraded mode."""
        self._in_recovery[session_id] = True
        self._recovery_step[session_id] = 0

    def is_in_recovery(self, session_id: str) -> bool:
        return self._in_recovery.get(session_id, False)

    def apply_recovery_ramp(
        self, session_id: str, confidence: float, lineage_id: UUID | None = None
    ) -> tuple[float, StabilityIntervention | None]:
        """Apply gradual recovery ramp to confidence."""
        if not self.is_in_recovery(session_id):
            return confidence, None

        step = self._recovery_step.get(session_id, 0)
        if step >= self.RECOVERY_RAMP_STEPS:
            self._in_recovery[session_id] = False
            return confidence, None

        # Ramp: step 0 = 33%, step 1 = 66%, step 2 = 100%
        ramp_factor = (step + 1) * self.RECOVERY_RAMP_FACTOR
        ramped = confidence * min(ramp_factor, 1.0)
        self._recovery_step[session_id] = step + 1

        intervention = StabilityIntervention(
            intervention_type="recovery_ramp",
            reason=f"step {step + 1}/{self.RECOVERY_RAMP_STEPS}, factor={ramp_factor:.2f}",
            original_value=confidence,
            corrected_value=ramped,
            lineage_id=lineage_id,
        )

        return ramped, intervention


class AdaptiveStabilizer:
    """Unified stabilization layer — wraps all stability components.

    Runtime actively prevents instability rather than just detecting it.
    All interventions are observable in replay.
    """

    def __init__(self) -> None:
        self.hysteresis = OrchestrationHysteresis()
        self.continuity = EmotionalContinuityDamper()
        self.confidence_guard = ConfidenceSpikePreventor()
        self.recovery = RecoveryStabilizer()
        self._metrics = StabilityMetrics()
        self._interventions: list[StabilityIntervention] = []

    def apply_state_stabilization(
        self, session_id: str, state: dict,
        confidence: float, signal_count: int,
        is_degraded: bool, lineage_id: UUID | None = None,
    ) -> tuple[dict, float, list[StabilityIntervention]]:
        """Apply all stabilization layers to a state.

        Returns (stabilized_state, stabilized_confidence, interventions).
        """
        interventions: list[StabilityIntervention] = []

        # 1. Emotional continuity damping
        state, cont_intervention = self.continuity.apply(
            session_id, state, lineage_id
        )
        if cont_intervention:
            interventions.append(cont_intervention)
            self._metrics.continuity_corrections += 1

        # 2. Confidence spike prevention
        confidence, conf_intervention = self.confidence_guard.apply(
            session_id, confidence, signal_count, is_degraded, lineage_id
        )
        if conf_intervention:
            interventions.append(conf_intervention)
            self._metrics.confidence_clamps += 1

        # 3. Recovery ramp (if in recovery)
        confidence, rec_intervention = self.recovery.apply_recovery_ramp(
            session_id, confidence, lineage_id
        )
        if rec_intervention:
            interventions.append(rec_intervention)
            self._metrics.degraded_recovery_interventions += 1

        # Track
        self._metrics.total_interventions += len(interventions)
        self._interventions.extend(interventions)
        if len(self._interventions) > 200:
            self._interventions = self._interventions[-100:]

        return state, confidence, interventions

    def check_orchestration_hysteresis(
        self, session_id: str, proposed_mode: str, confidence: float
    ) -> tuple[bool, str]:
        """Check if orchestration mode change is allowed."""
        allowed, reason = self.hysteresis.should_allow_change(
            session_id, proposed_mode, confidence
        )
        if not allowed:
            self._metrics.oscillation_preventions += 1
        return allowed, reason

    def commit_mode_change(
        self, session_id: str, mode: str, confidence: float
    ) -> None:
        """Record a committed mode change."""
        self.hysteresis.record_change(session_id, mode, confidence)

    def get_metrics(self) -> StabilityMetrics:
        """Get aggregate stability metrics."""
        return self._metrics

    def get_recent_interventions(self, n: int = 10) -> list[StabilityIntervention]:
        """Get N most recent interventions."""
        return self._interventions[-n:]
