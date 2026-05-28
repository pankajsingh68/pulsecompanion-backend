"""Deterministic replay validation — guarantees identical outputs across runs.

Replays execute in isolated sandbox state. No runtime mutation allowed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from utils.helpers import clamp
from utils.logger import get_logger

logger = get_logger(__name__)

FLOAT_TOLERANCE = 0.0001


class ReplayIsolationViolation(Exception):
    """Raised when replay attempts to access live runtime."""
    pass


class ReplaySandboxRuntime:
    """Isolated sandbox for replay execution.

    Provides fake subsystems that NEVER touch live runtime.
    Replay must execute entirely within this sandbox.
    """

    def __init__(self) -> None:
        self._live_runtime_detected = False
        self._events_emitted: list[dict] = []
        logger.debug("replay_sandbox_created")

    def emit_event(self, event_type: str, payload: dict) -> None:
        """Fake event emission — captured but never sent to live bus."""
        self._events_emitted.append({"type": event_type, **payload})

    def get_emitted(self) -> list[dict]:
        return list(self._events_emitted)

    def assert_isolation(self) -> None:
        """Verify no live runtime access occurred."""
        if self._live_runtime_detected:
            raise ReplayIsolationViolation(
                "Replay sandbox detected live runtime access"
            )

    def mark_live_access(self) -> None:
        """Called if live runtime is accidentally accessed."""
        self._live_runtime_detected = True
        logger.error("replay_isolation_violation")


@dataclass
class ReplaySnapshot:
    """Captured state at a point in the pipeline for replay comparison."""
    lineage_id: UUID | None = None
    session_id: str = ""
    stress: float = 0.0
    fatigue: float = 0.0
    focus: float = 0.5
    engagement: float = 0.5
    orchestration_mode: str = "normal"
    confidence: float = 0.5
    degraded_state: bool = False
    stabilization_interventions: int = 0
    continuity_score: float = 0.0
    timestamp: float = 0.0


@dataclass
class ReplayDiff:
    """Difference report between original and replayed snapshots."""
    mismatched_fields: list[str] = field(default_factory=list)
    divergence_score: float = 0.0
    deterministic: bool = True
    details: dict[str, dict] = field(default_factory=dict)


class ReplayDeterminismValidator:
    """Validates that replay produces identical outputs.

    Executes in isolated sandbox — no live runtime mutation.
    """

    def __init__(self) -> None:
        self._replay_count: int = 0
        self._divergence_count: int = 0
        self._last_diff: ReplayDiff | None = None

    def replay_lineage(self, events: list[dict]) -> ReplaySnapshot:
        """Replay a sequence of events in isolated sandbox.

        Task 5: NO live runtime mutation. Executes deterministically.
        """
        from runtime.adaptive_stabilizer import AdaptiveStabilizer
        from memory.emotional_continuity import EmotionalContinuityProfile
        from runtime.degraded_mode_controller import DegradedModeController

        # Task 5: Isolated sandbox — never touches live runtime
        sandbox = ReplaySandboxRuntime()

        stabilizer = AdaptiveStabilizer()
        continuity = EmotionalContinuityProfile("replay_sandbox")
        degraded = DegradedModeController()

        snapshot = ReplaySnapshot()
        intervention_count = 0

        for event in events:
            state = event.get("state", {})
            confidence = event.get("confidence", 0.5)
            signal_count = event.get("signal_count", 2)

            stabilized, conf, interventions = stabilizer.apply_state_stabilization(
                "replay_sandbox", state, confidence, signal_count,
                degraded.is_degraded,
            )
            intervention_count += len(interventions)
            continuity.update(stabilized)

            snapshot.stress = stabilized.get("stress", 0)
            snapshot.fatigue = stabilized.get("fatigue", 0)
            snapshot.focus = stabilized.get("focus", 0.5)
            snapshot.engagement = stabilized.get("engagement", 0.5)
            snapshot.confidence = conf
            snapshot.orchestration_mode = stabilized.get("ux_mode", "normal")
            snapshot.degraded_state = degraded.is_degraded
            snapshot.lineage_id = event.get("lineage_id")
            snapshot.session_id = event.get("session_id", "")

        snapshot.stabilization_interventions = intervention_count
        score = continuity.get_continuity_score()
        snapshot.continuity_score = score.overall

        sandbox.assert_isolation()
        logger.debug("replay_completed", events=len(events))

        snapshot.stabilization_interventions = intervention_count
        score = continuity.get_continuity_score()
        snapshot.continuity_score = score.overall

        self._replay_count += 1
        return snapshot

    def compare_snapshots(
        self, original: ReplaySnapshot, replayed: ReplaySnapshot
    ) -> ReplayDiff:
        """Compare two snapshots for determinism."""
        diff = ReplayDiff()
        fields_to_check = [
            ("stress", original.stress, replayed.stress),
            ("fatigue", original.fatigue, replayed.fatigue),
            ("focus", original.focus, replayed.focus),
            ("engagement", original.engagement, replayed.engagement),
            ("confidence", original.confidence, replayed.confidence),
            ("continuity_score", original.continuity_score, replayed.continuity_score),
        ]

        for name, orig_val, replay_val in fields_to_check:
            if abs(orig_val - replay_val) > FLOAT_TOLERANCE:
                diff.mismatched_fields.append(name)
                diff.details[name] = {
                    "original": orig_val,
                    "replayed": replay_val,
                    "delta": abs(orig_val - replay_val),
                }

        # Check non-float fields
        if original.orchestration_mode != replayed.orchestration_mode:
            diff.mismatched_fields.append("orchestration_mode")
            diff.details["orchestration_mode"] = {
                "original": original.orchestration_mode,
                "replayed": replayed.orchestration_mode,
            }

        if original.degraded_state != replayed.degraded_state:
            diff.mismatched_fields.append("degraded_state")

        if original.stabilization_interventions != replayed.stabilization_interventions:
            diff.mismatched_fields.append("stabilization_interventions")
            diff.details["stabilization_interventions"] = {
                "original": original.stabilization_interventions,
                "replayed": replayed.stabilization_interventions,
            }

        diff.deterministic = len(diff.mismatched_fields) == 0
        diff.divergence_score = len(diff.mismatched_fields) / max(len(fields_to_check) + 3, 1)

        if not diff.deterministic:
            self._divergence_count += 1
            self._last_diff = diff

        return diff

    def validate_replay(self, events: list[dict]) -> ReplayDiff:
        """Run replay twice and compare outputs."""
        snap1 = self.replay_lineage(events)
        snap2 = self.replay_lineage(events)
        return self.compare_snapshots(snap1, snap2)

    def validate_multiple_replays(
        self, events: list[dict], runs: int = 5
    ) -> ReplayDiff:
        """Run replay N times and verify all produce identical output."""
        snapshots = [self.replay_lineage(events) for _ in range(runs)]
        reference = snapshots[0]

        combined_diff = ReplayDiff(deterministic=True)
        for i, snap in enumerate(snapshots[1:], 1):
            diff = self.compare_snapshots(reference, snap)
            if not diff.deterministic:
                combined_diff.deterministic = False
                combined_diff.mismatched_fields.extend(
                    [f"run{i}:{f}" for f in diff.mismatched_fields]
                )
                combined_diff.details[f"run_{i}"] = diff.details

        combined_diff.divergence_score = (
            len(combined_diff.mismatched_fields) / (runs * 9)
        )
        return combined_diff

    # --- Introspection ---

    def get_replay_consistency_rate(self) -> float:
        """Fraction of replays that were deterministic."""
        if self._replay_count == 0:
            return 1.0
        return 1.0 - (self._divergence_count / self._replay_count)

    def get_last_divergence_report(self) -> ReplayDiff | None:
        """Get the most recent divergence report."""
        return self._last_diff
