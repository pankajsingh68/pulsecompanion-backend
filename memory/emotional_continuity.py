"""Longitudinal emotional continuity memory.

Tracks emotional patterns across sessions: baseline drift, fatigue trends,
engagement patterns, recovery behavior, adaptation responsiveness.
All state changes are replayable deterministically.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from utils.helpers import clamp
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class EmotionalTrajectory:
    """Longitudinal emotional trajectory for a user/session."""
    session_id: str
    stress_baseline: float = 0.3
    fatigue_baseline: float = 0.2
    engagement_baseline: float = 0.5
    recovery_rate: float = 0.5  # how fast stress drops after peaks
    adaptation_responsiveness: float = 0.5  # how well user responds to interventions
    volatility: float = 0.3  # emotional state variance
    # History
    stress_history: list[float] = field(default_factory=list)
    fatigue_history: list[float] = field(default_factory=list)
    engagement_history: list[float] = field(default_factory=list)
    update_count: int = 0


@dataclass
class BaselineShift:
    """Detected baseline shift event."""
    metric: str
    old_baseline: float
    new_baseline: float
    shift_magnitude: float
    detected_at: float = field(default_factory=time.monotonic)


@dataclass
class ContinuityScore:
    """Composite continuity scoring."""
    emotional_continuity: float = 0.8  # trajectory smoothness
    adaptation_stability: float = 0.7  # how stable adaptations are
    longitudinal_confidence: float = 0.5  # confidence in longitudinal model
    overall: float = 0.7


class BaselineShiftDetector:
    """Detects abrupt baseline shifts in emotional metrics."""

    SHIFT_THRESHOLD = 0.15  # minimum shift to flag
    WINDOW_SIZE = 10  # samples to compare

    def detect(self, history: list[float], current_baseline: float) -> BaselineShift | None:
        """Detect if recent values represent a baseline shift."""
        if len(history) < self.WINDOW_SIZE * 2:
            return None

        old_window = history[-self.WINDOW_SIZE * 2:-self.WINDOW_SIZE]
        new_window = history[-self.WINDOW_SIZE:]

        old_avg = sum(old_window) / len(old_window)
        new_avg = sum(new_window) / len(new_window)
        shift = abs(new_avg - old_avg)

        if shift >= self.SHIFT_THRESHOLD:
            return BaselineShift(
                metric="detected",
                old_baseline=round(old_avg, 3),
                new_baseline=round(new_avg, 3),
                shift_magnitude=round(shift, 3),
            )
        return None


class AdaptationHistoryTracker:
    """Tracks how the user responds to adaptive interventions over time."""

    def __init__(self) -> None:
        self._interventions: dict[str, list[dict]] = {}
        self._responsiveness: dict[str, float] = {}

    def record_intervention(
        self, session_id: str, intervention_type: str,
        stress_before: float, stress_after: float,
    ) -> None:
        """Record an intervention and its effect."""
        if session_id not in self._interventions:
            self._interventions[session_id] = []

        effect = stress_before - stress_after  # positive = stress reduced
        self._interventions[session_id].append({
            "type": intervention_type,
            "effect": round(effect, 3),
            "timestamp": time.monotonic(),
        })

        # Update responsiveness (EMA)
        prev = self._responsiveness.get(session_id, 0.5)
        effectiveness = clamp(effect * 2)  # normalize
        self._responsiveness[session_id] = 0.3 * effectiveness + 0.7 * prev

    def get_responsiveness(self, session_id: str) -> float:
        """Get adaptation responsiveness score for session."""
        return self._responsiveness.get(session_id, 0.5)

    def get_history(self, session_id: str) -> list[dict]:
        return self._interventions.get(session_id, [])


class EmotionalContinuityProfile:
    """Per-session longitudinal emotional profile.

    Tracks patterns across the session lifetime.
    All state changes are deterministic and replayable.
    """

    ALPHA = 0.1  # slow baseline adaptation

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self.trajectory = EmotionalTrajectory(session_id=session_id)
        self.shift_detector = BaselineShiftDetector()
        self.adaptation_tracker = AdaptationHistoryTracker()
        self._detected_shifts: list[BaselineShift] = []
        self._patterns: list[str] = []

    def update(self, state: dict) -> list[str]:
        """Update profile with new state. Returns detected patterns."""
        stress = state.get("stress", 0.3)
        fatigue = state.get("fatigue", 0.2)
        engagement = state.get("engagement", 0.5)

        self.trajectory.update_count += 1
        self.trajectory.stress_history.append(stress)
        self.trajectory.fatigue_history.append(fatigue)
        self.trajectory.engagement_history.append(engagement)

        # Keep bounded history
        max_hist = 200
        if len(self.trajectory.stress_history) > max_hist:
            self.trajectory.stress_history = self.trajectory.stress_history[-max_hist:]
            self.trajectory.fatigue_history = self.trajectory.fatigue_history[-max_hist:]
            self.trajectory.engagement_history = self.trajectory.engagement_history[-max_hist:]

        # Update baselines (EMA)
        self.trajectory.stress_baseline = (
            self.ALPHA * stress + (1 - self.ALPHA) * self.trajectory.stress_baseline
        )
        self.trajectory.fatigue_baseline = (
            self.ALPHA * fatigue + (1 - self.ALPHA) * self.trajectory.fatigue_baseline
        )
        self.trajectory.engagement_baseline = (
            self.ALPHA * engagement + (1 - self.ALPHA) * self.trajectory.engagement_baseline
        )

        # Detect patterns
        patterns: list[str] = []

        # Baseline shift detection
        shift = self.shift_detector.detect(
            self.trajectory.stress_history, self.trajectory.stress_baseline
        )
        if shift:
            shift.metric = "stress"
            self._detected_shifts.append(shift)
            patterns.append("stress_baseline_shift")

        # Chronic overload detection
        if self.trajectory.update_count >= 10:
            recent_stress = self.trajectory.stress_history[-10:]
            if all(s > 0.6 for s in recent_stress):
                patterns.append("chronic_overload")

        # Emotional volatility
        if len(self.trajectory.stress_history) >= 5:
            recent = self.trajectory.stress_history[-5:]
            variance = sum((s - sum(recent)/5)**2 for s in recent) / 5
            self.trajectory.volatility = clamp(variance * 10)
            if variance > 0.04:
                patterns.append("high_volatility")

        # Recovery behavior
        if len(self.trajectory.stress_history) >= 3:
            last3 = self.trajectory.stress_history[-3:]
            if last3[0] > 0.6 and last3[-1] < 0.4:
                self.trajectory.recovery_rate = clamp(
                    0.3 * 0.8 + 0.7 * self.trajectory.recovery_rate
                )
                patterns.append("recovery_detected")

        self._patterns = patterns
        return patterns

    def get_continuity_score(self, is_degraded: bool = False) -> ContinuityScore:
        """Compute longitudinal continuity scores."""
        # Emotional continuity: inverse of volatility
        continuity = clamp(1.0 - self.trajectory.volatility)

        # Adaptation stability: based on responsiveness
        responsiveness = self.adaptation_tracker.get_responsiveness(self.session_id)
        stability = clamp(responsiveness * 0.6 + (1.0 - self.trajectory.volatility) * 0.4)

        # Longitudinal confidence: based on sample count
        sample_confidence = clamp(self.trajectory.update_count / 20.0)
        if is_degraded:
            sample_confidence *= 0.5  # degraded mode reduces confidence

        overall = continuity * 0.4 + stability * 0.35 + sample_confidence * 0.25

        return ContinuityScore(
            emotional_continuity=round(continuity, 3),
            adaptation_stability=round(stability, 3),
            longitudinal_confidence=round(sample_confidence, 3),
            overall=round(overall, 3),
        )

    # --- Introspection ---

    async def get_emotional_trajectory(self) -> dict:
        """Get current emotional trajectory."""
        return {
            "session_id": self.session_id,
            "stress_baseline": round(self.trajectory.stress_baseline, 3),
            "fatigue_baseline": round(self.trajectory.fatigue_baseline, 3),
            "engagement_baseline": round(self.trajectory.engagement_baseline, 3),
            "recovery_rate": round(self.trajectory.recovery_rate, 3),
            "volatility": round(self.trajectory.volatility, 3),
            "update_count": self.trajectory.update_count,
            "detected_shifts": len(self._detected_shifts),
            "recent_patterns": self._patterns,
        }

    async def get_baseline_drift(self) -> dict:
        """Get baseline drift information."""
        return {
            "shifts_detected": len(self._detected_shifts),
            "recent_shifts": [
                {"metric": s.metric, "magnitude": s.shift_magnitude}
                for s in self._detected_shifts[-5:]
            ],
            "stress_baseline": round(self.trajectory.stress_baseline, 3),
            "fatigue_baseline": round(self.trajectory.fatigue_baseline, 3),
        }

    async def get_longitudinal_stability(self) -> dict:
        """Get longitudinal stability metrics."""
        score = self.get_continuity_score()
        return {
            "emotional_continuity": score.emotional_continuity,
            "adaptation_stability": score.adaptation_stability,
            "longitudinal_confidence": score.longitudinal_confidence,
            "overall": score.overall,
            "volatility": round(self.trajectory.volatility, 3),
            "responsiveness": self.adaptation_tracker.get_responsiveness(self.session_id),
        }
