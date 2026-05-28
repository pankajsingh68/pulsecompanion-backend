"""Emotional Fusion Engine — multimodal signal fusion with contradiction resolution.

Accepts multimodal emotional signals, resolves conflicts, smooths over time,
produces one UnifiedEmotionalState per cycle. Deterministic and replay-safe.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from utils.logger import get_logger

logger = get_logger(__name__)

# Increment on any logic change — replay uses this to detect drift
FUSION_VERSION = 1

# Tracked dimensions
DIMENSIONS = ("stress", "engagement", "emotional_openness", "cognitive_load")

# Source reliability weights
BASE_WEIGHTS: dict[str, float] = {
    "voice": 0.35,
    "pacing": 0.25,
    "text": 0.25,
    "silence": 0.10,
    "interruption": 0.05,
}

STRESS_OVERRIDE_WEIGHTS: dict[str, float] = {
    "voice": 0.45,
    "pacing": 0.35,
    "text": 0.10,
    "silence": 0.05,
    "interruption": 0.05,
}

# Smoothing
EMA_ALPHA_NORMAL = 0.3
EMA_ALPHA_DEGRADED = 0.15

# Rate-of-change clamp
MAX_DELTA_PER_CYCLE = 0.15

# Contradiction threshold
CONTRADICTION_THRESHOLD = 0.4
CONTRADICTION_MIN_CONFIDENCE = 0.5

# Recovery
RECOVERY_WINDOW = 10
RECOVERY_RISE_RATE = 0.05
RECOVERY_DROP_ON_SPIKE = 0.3


@dataclass(frozen=True)
class EmotionalSignal:
    """Input signal from a single modality."""
    source: str
    confidence: float
    timestamp: float
    values: dict[str, float]


@dataclass(frozen=True)
class UnifiedEmotionalState:
    """Output: single fused emotional state per cycle."""
    stress: float
    engagement: float
    emotional_openness: float
    cognitive_load: float
    recovery_state: float
    confidence: float
    signal_stability: float
    dominant_source: str
    fusion_version: int


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


class EmotionalFusionEngine:
    """Fuses multimodal emotional signals into a single unified state.

    Deterministic: given identical signal sequence and initial state,
    output sequence is byte-identical across runs.
    """

    def __init__(self) -> None:
        # Previous outputs for smoothing
        self._prev_state: dict[str, float] = {
            "stress": 0.3,
            "engagement": 0.5,
            "emotional_openness": 0.5,
            "cognitive_load": 0.3,
        }
        self._prev_smoothed: dict[str, float] = dict(self._prev_state)
        self._prev_output: UnifiedEmotionalState | None = None

        # Recovery tracking
        self._stress_history: deque[float] = deque(maxlen=RECOVERY_WINDOW)
        self._recovery_state: float = 0.5
        self._consecutive_decline: int = 0

        # Bounded collections
        self._signal_history: deque[EmotionalSignal] = deque(maxlen=200)
        self._smoothing_history: dict[str, deque] = {
            dim: deque(maxlen=50) for dim in DIMENSIONS
        }
        self._contradiction_log: deque[dict] = deque(maxlen=50)
        self._diagnostics_buffer: deque[dict] = deque(maxlen=100)

        # Diagnostics counters
        self._contradiction_count: int = 0
        self._smoothing_interventions: int = 0
        self._degraded_operation_count: int = 0
        self._dominant_source_history: deque[str] = deque(maxlen=50)

    def process_cycle(
        self, signals: list[EmotionalSignal], degraded: bool = False
    ) -> UnifiedEmotionalState:
        """Process one fusion cycle.

        Args:
            signals: All available emotional signals for this cycle.
            degraded: If True, operate in degraded mode.

        Returns:
            Frozen UnifiedEmotionalState. Never raises. Never returns None.
        """
        # Store signals
        for s in signals:
            self._signal_history.append(s)

        # Filter sources in degraded mode
        if degraded:
            self._degraded_operation_count += 1
            signals = [s for s in signals if s.source not in ("silence", "interruption")]

        alpha = EMA_ALPHA_DEGRADED if degraded else EMA_ALPHA_NORMAL

        # Determine current stress for weight selection
        current_stress = self._prev_state.get("stress", 0.3)

        # Step 1: Select weights
        weights = (
            STRESS_OVERRIDE_WEIGHTS if current_stress > 0.6 else BASE_WEIGHTS
        )

        # Step 2: Confidence-weighted average per dimension
        raw_values: dict[str, float] = {}
        source_contributions: dict[str, float] = {}

        for dim in DIMENSIONS:
            numerator = 0.0
            denominator = 0.0
            for sig in signals:
                if dim not in sig.values:
                    continue
                w = weights.get(sig.source, 0.05)
                contribution = sig.values[dim] * sig.confidence * w
                numerator += contribution
                denominator += sig.confidence * w
                # Track dominant source
                source_contributions[sig.source] = (
                    source_contributions.get(sig.source, 0.0) + abs(contribution)
                )

            if denominator > 0:
                raw_values[dim] = numerator / denominator
            else:
                raw_values[dim] = self._prev_state.get(dim, 0.5)

        # Determine dominant source
        dominant_source = "none"
        if source_contributions:
            dominant_source = max(source_contributions, key=source_contributions.get)
        self._dominant_source_history.append(dominant_source)

        # Step 3: Contradiction detection
        conflicted_dims: list[str] = []
        confidence_output = 1.0
        signal_stability = 1.0

        for dim in DIMENSIONS:
            dim_values = []
            for sig in signals:
                if dim in sig.values and sig.confidence > CONTRADICTION_MIN_CONFIDENCE:
                    dim_values.append(sig.values[dim])

            if len(dim_values) >= 2:
                spread = max(dim_values) - min(dim_values)
                if spread > CONTRADICTION_THRESHOLD:
                    conflicted_dims.append(dim)
                    self._contradiction_count += 1
                    self._contradiction_log.append({
                        "dim": dim,
                        "spread": round(spread, 3),
                        "values": [round(v, 3) for v in dim_values],
                    })

        # Apply contradiction penalties
        for _ in conflicted_dims:
            confidence_output = max(0.2, confidence_output - 0.15)
            signal_stability = max(0.1, signal_stability - 0.2)

        # Dampen conflicted dimensions toward previous state
        dampened: dict[str, float] = {}
        for dim in DIMENSIONS:
            if dim in conflicted_dims:
                dampened[dim] = 0.6 * raw_values[dim] + 0.4 * self._prev_state.get(dim, 0.5)
                self._smoothing_interventions += 1
            else:
                dampened[dim] = raw_values[dim]

        # Step 4: EMA smoothing
        smoothed: dict[str, float] = {}
        for dim in DIMENSIONS:
            prev_smooth = self._prev_smoothed.get(dim, 0.5)
            smoothed[dim] = alpha * dampened[dim] + (1 - alpha) * prev_smooth
            self._smoothing_history[dim].append(smoothed[dim])

        # Step 5: Rate-of-change clamping
        final: dict[str, float] = {}
        for dim in DIMENSIONS:
            prev_val = self._prev_state.get(dim, 0.5)
            lo = prev_val - MAX_DELTA_PER_CYCLE
            hi = prev_val + MAX_DELTA_PER_CYCLE
            final[dim] = _clamp(smoothed[dim], lo, hi)
            # Ensure within [0, 1]
            final[dim] = _clamp(final[dim])

        # Recovery state calculation
        self._stress_history.append(final["stress"])
        self._update_recovery(final["stress"])

        # Degraded mode confidence cap
        if degraded:
            confidence_output = min(confidence_output, 0.6)

        # Build output
        output = UnifiedEmotionalState(
            stress=round(final["stress"], 6),
            engagement=round(final["engagement"], 6),
            emotional_openness=round(final["emotional_openness"], 6),
            cognitive_load=round(final["cognitive_load"], 6),
            recovery_state=round(_clamp(self._recovery_state), 6),
            confidence=round(_clamp(confidence_output), 6),
            signal_stability=round(_clamp(signal_stability), 6),
            dominant_source=dominant_source,
            fusion_version=FUSION_VERSION,
        )

        # Update previous state
        self._prev_state = dict(final)
        self._prev_smoothed = dict(smoothed)
        self._prev_output = output

        # Diagnostics
        self._diagnostics_buffer.append({
            "conflicted": conflicted_dims,
            "confidence": output.confidence,
            "dominant": dominant_source,
            "degraded": degraded,
        })

        return output

    def _update_recovery(self, current_stress: float) -> None:
        """Update recovery_state based on stress trajectory."""
        if len(self._stress_history) < 2:
            return

        prev_stress = self._stress_history[-2] if len(self._stress_history) >= 2 else current_stress

        # Detect spike
        if current_stress - prev_stress > 0.15:
            self._recovery_state = max(0.0, self._recovery_state - RECOVERY_DROP_ON_SPIKE)
            self._consecutive_decline = 0
            return

        # Detect decline
        if current_stress < prev_stress:
            self._consecutive_decline += 1
        else:
            self._consecutive_decline = max(0, self._consecutive_decline - 1)

        # Rise if declining for 5+ cycles
        if self._consecutive_decline >= 5:
            self._recovery_state = min(1.0, self._recovery_state + RECOVERY_RISE_RATE)

    # --- Observability APIs (read-only, no side effects) ---

    async def get_current_emotional_state(self) -> UnifiedEmotionalState | None:
        """Get the most recent fused state."""
        return self._prev_output

    async def get_signal_health(self) -> dict[str, float]:
        """Per-source confidence averages over last 20 cycles."""
        source_confs: dict[str, list[float]] = {}
        recent = list(self._signal_history)[-100:]  # last ~20 cycles worth
        for sig in recent:
            if sig.source not in source_confs:
                source_confs[sig.source] = []
            source_confs[sig.source].append(sig.confidence)

        return {
            source: round(sum(confs) / len(confs), 3)
            for source, confs in source_confs.items()
            if confs
        }

    async def get_fusion_diagnostics(self) -> dict:
        """Fusion diagnostics summary."""
        return {
            "contradiction_count": self._contradiction_count,
            "smoothing_interventions": self._smoothing_interventions,
            "confidence_drift": round(
                self._prev_output.confidence if self._prev_output else 1.0, 3
            ),
            "dominant_source_history": list(self._dominant_source_history)[-10:],
            "degraded_operation_count": self._degraded_operation_count,
            "signal_history_size": len(self._signal_history),
            "fusion_version": FUSION_VERSION,
        }
