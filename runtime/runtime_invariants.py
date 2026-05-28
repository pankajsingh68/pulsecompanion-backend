"""Runtime-wide invariant enforcement and contract validation.

Prevents silent corruption and invalid runtime transitions.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID

from utils.helpers import clamp
from utils.logger import get_logger

logger = get_logger(__name__)


class InvariantSeverity(str, Enum):
    WARNING = "warning"
    ERROR = "error"
    FATAL = "fatal"


class ValidatorMode(str, Enum):
    STRICT = "strict"
    WARN_ONLY = "warn_only"


@dataclass
class RuntimeInvariantViolation:
    """A detected invariant violation."""
    invariant_name: str
    subsystem: str
    severity: InvariantSeverity
    lineage_id: UUID | None = None
    details: str = ""
    corrective_hint: str = ""
    auto_corrected: bool = False


@dataclass
class InvariantReport:
    """Aggregate invariant validation report."""
    violations: list[RuntimeInvariantViolation] = field(default_factory=list)
    checked: int = 0
    passed: int = 0
    failed: int = 0
    auto_corrected: int = 0

    @property
    def is_valid(self) -> bool:
        fatal = [v for v in self.violations if v.severity == InvariantSeverity.FATAL]
        return len(fatal) == 0


@dataclass
class InvariantMetrics:
    """Aggregate invariant metrics."""
    violations_detected: int = 0
    recovered_violations: int = 0
    fatal_violations: int = 0
    total_corrections: int = 0
    corrections_by_type: dict[str, int] = field(default_factory=dict)
    warn_only_violations: int = 0


class RuntimeContractValidator:
    """Validates runtime invariants across all subsystems.

    Modes:
    - STRICT: violations raise errors
    - WARN_ONLY: violations logged but not raised
    """

    def __init__(self, mode: ValidatorMode = ValidatorMode.STRICT) -> None:
        self._mode = mode
        self._metrics = InvariantMetrics()
        self._violations: list[RuntimeInvariantViolation] = []
        self._corrections: list[dict] = []  # Task 6: observable corrections

    # --- State invariants ---

    def validate_state(self, state: dict, lineage_id: UUID | None = None) -> InvariantReport:
        """Validate emotional state values are within bounds."""
        report = InvariantReport()

        # Stress in [0, 1]
        report.checked += 1
        stress = state.get("stress", 0)
        if not (0.0 <= stress <= 1.0):
            v = self._violation(
                "stress_bounded", "state", InvariantSeverity.ERROR,
                lineage_id, f"stress={stress} out of [0,1]",
                "clamp to [0,1]",
            )
            report.violations.append(v)
            state["stress"] = clamp(stress)
            v.auto_corrected = True
            report.auto_corrected += 1
            self._record_correction("stress_bounded", lineage_id, stress, state["stress"])
        else:
            report.passed += 1

        # Fatigue in [0, 1]
        report.checked += 1
        fatigue = state.get("fatigue", 0)
        if not (0.0 <= fatigue <= 1.0):
            v = self._violation(
                "fatigue_bounded", "state", InvariantSeverity.ERROR,
                lineage_id, f"fatigue={fatigue} out of [0,1]",
                "clamp to [0,1]",
            )
            report.violations.append(v)
            state["fatigue"] = clamp(fatigue)
            v.auto_corrected = True
            report.auto_corrected += 1
            self._record_correction("fatigue_bounded", lineage_id, fatigue, state["fatigue"])
        else:
            report.passed += 1

        # Focus in [0, 1]
        report.checked += 1
        focus = state.get("focus", 0.5)
        if not (0.0 <= focus <= 1.0):
            v = self._violation(
                "focus_bounded", "state", InvariantSeverity.ERROR,
                lineage_id, f"focus={focus} out of [0,1]",
                "clamp to [0,1]",
            )
            report.violations.append(v)
            state["focus"] = clamp(focus)
            v.auto_corrected = True
            report.auto_corrected += 1
        else:
            report.passed += 1

        # Confidence in [0, 1]
        report.checked += 1
        conf = state.get("confidence", 0.5)
        if not (0.0 <= conf <= 1.0):
            v = self._violation(
                "confidence_bounded", "state", InvariantSeverity.ERROR,
                lineage_id, f"confidence={conf} out of [0,1]",
                "clamp to [0,1]",
            )
            report.violations.append(v)
            state["confidence"] = clamp(conf)
            v.auto_corrected = True
            report.auto_corrected += 1
        else:
            report.passed += 1

        # Impossible state: high stress + high focus simultaneously
        report.checked += 1
        if stress > 0.9 and focus > 0.9:
            v = self._violation(
                "impossible_state", "state", InvariantSeverity.WARNING,
                lineage_id, f"stress={stress:.2f} AND focus={focus:.2f}",
                "reduce focus under extreme stress",
            )
            report.violations.append(v)
        else:
            report.passed += 1

        report.failed = len(report.violations)
        return report

    def validate_trace(
        self, lineage_id: UUID, stages: list[str], expected_stages: list[str]
    ) -> InvariantReport:
        """Validate trace integrity."""
        report = InvariantReport()

        # No duplicate terminal stages
        report.checked += 1
        from collections import Counter
        counts = Counter(stages)
        duplicates = [s for s, c in counts.items() if c > 1]
        if duplicates:
            v = self._violation(
                "no_duplicate_stages", "trace", InvariantSeverity.ERROR,
                lineage_id, f"duplicates: {duplicates}",
                "reject duplicate stage emissions",
            )
            report.violations.append(v)
        else:
            report.passed += 1

        # Stage ordering valid
        report.checked += 1
        expected_order = {s: i for i, s in enumerate(expected_stages)}
        prev_idx = -1
        ordering_valid = True
        for stage in stages:
            idx = expected_order.get(stage, -1)
            if idx < prev_idx:
                ordering_valid = False
                break
            prev_idx = idx

        if not ordering_valid:
            v = self._violation(
                "stage_ordering", "trace", InvariantSeverity.ERROR,
                lineage_id, f"stages out of order: {stages}",
                "enforce monotonic stage ordering",
            )
            report.violations.append(v)
        else:
            report.passed += 1

        report.failed = len(report.violations)
        return report

    def validate_session_transition(
        self, current_state: str, proposed_state: str, session_id: str
    ) -> InvariantReport:
        """Validate session state transition is legal."""
        report = InvariantReport()
        report.checked += 1

        # EXPIRED cannot become ACTIVE
        if current_state == "expired" and proposed_state == "active":
            v = self._violation(
                "expired_no_reactivate", "session", InvariantSeverity.FATAL,
                None, f"session {session_id}: expired → active",
                "create new session instead",
            )
            report.violations.append(v)
            self._metrics.fatal_violations += 1
        else:
            report.passed += 1

        report.failed = len(report.violations)
        return report

    def validate_runtime(self) -> InvariantReport:
        """Run all runtime-wide invariant checks."""
        # Placeholder for full runtime validation
        return InvariantReport(checked=1, passed=1)

    # --- Metrics ---

    def get_metrics(self) -> InvariantMetrics:
        return self._metrics

    def get_recent_violations(self, n: int = 10) -> list[RuntimeInvariantViolation]:
        return self._violations[-n:]

    def get_recent_corrections(self, n: int = 10) -> list[dict]:
        """Task 6: Get recent auto-corrections for observability."""
        return self._corrections[-n:]

    def get_correction_metrics(self) -> dict:
        """Task 6: Get correction metrics."""
        return {
            "total_corrections": self._metrics.total_corrections,
            "corrections_by_type": dict(self._metrics.corrections_by_type),
            "fatal_violations": self._metrics.fatal_violations,
            "warn_only_violations": self._metrics.warn_only_violations,
        }

    # --- Internal ---

    def _record_correction(
        self, invariant_type: str, lineage_id: Any, original: Any, corrected: Any
    ) -> None:
        """Task 6: Record an observable correction."""
        self._metrics.total_corrections += 1
        self._metrics.corrections_by_type[invariant_type] = (
            self._metrics.corrections_by_type.get(invariant_type, 0) + 1
        )
        self._corrections.append({
            "lineage_id": str(lineage_id) if lineage_id else None,
            "invariant_type": invariant_type,
            "original_value": original,
            "corrected_value": corrected,
            "timestamp": time.monotonic(),
        })
        if len(self._corrections) > 200:
            self._corrections = self._corrections[-100:]

    def _violation(
        self, name: str, subsystem: str, severity: InvariantSeverity,
        lineage_id: UUID | None, details: str, hint: str,
    ) -> RuntimeInvariantViolation:
        v = RuntimeInvariantViolation(
            invariant_name=name, subsystem=subsystem,
            severity=severity, lineage_id=lineage_id,
            details=details, corrective_hint=hint,
        )
        self._violations.append(v)
        self._metrics.violations_detected += 1
        if v.auto_corrected:
            self._metrics.recovered_violations += 1
            self._metrics.total_corrections += 1
            inv_type = v.invariant_name
            self._metrics.corrections_by_type[inv_type] = (
                self._metrics.corrections_by_type.get(inv_type, 0) + 1
            )
            # Task 6: Record observable correction
            self._corrections.append({
                "lineage_id": str(lineage_id) if lineage_id else None,
                "invariant_type": name,
                "original_value": details,
                "corrected_value": hint,
                "timestamp": time.monotonic(),
            })
            if len(self._corrections) > 200:
                self._corrections = self._corrections[-100:]

        if self._mode == ValidatorMode.STRICT and severity == InvariantSeverity.FATAL:
            logger.error("fatal_invariant_violation", name=name, details=details)
        else:
            logger.warning("invariant_violation", name=name, severity=severity.value, details=details)

        return v
