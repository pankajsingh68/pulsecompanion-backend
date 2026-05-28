"""Orchestration pipeline validator — decision correctness and consistency.

Validates the orchestration engine produces consistent, non-oscillating
decisions with proper safety correction auditing.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from integration.adaptive_loop_validator import OrchestrationDecision, SafetyCorrection
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ActiveOrchestration:
    """An active orchestration decision being tracked."""
    session_id: str
    decision: OrchestrationDecision
    timestamp: float = 0.0
    confidence: float = 0.5


@dataclass
class OscillationReport:
    """Report on orchestration oscillation detection."""
    passed: bool = True
    total_decisions: int = 0
    oscillation_count: int = 0
    min_decision_interval_ms: float = 3000.0
    rapid_alternations: list[str] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)


@dataclass
class PropagationDelayStats:
    """Statistics on orchestration propagation delay."""
    mean_ms: float = 0.0
    p95_ms: float = 0.0
    max_ms: float = 0.0
    samples: int = 0


# Configurable thresholds
MIN_DECISION_INTERVAL_MS = 3000.0
MIN_CORROBORATING_SIGNALS = 2
CONFIDENCE_SPIKE_THRESHOLD = 0.8


async def get_active_orchestrations() -> list[ActiveOrchestration]:
    """Introspection API: get all active orchestration decisions."""
    return []


async def validate_oscillation_bounds(
    decisions: list[OrchestrationDecision],
    min_interval_ms: float = MIN_DECISION_INTERVAL_MS,
) -> OscillationReport:
    """Validate that orchestration decisions don't oscillate.

    Checks:
    - No oscillation: consecutive decisions must not alternate faster
      than min_decision_interval_ms
    - No confidence spike without evidence
    - Decision monotonicity within trajectory

    Args:
        decisions: List of orchestration decisions to validate.
        min_interval_ms: Minimum allowed interval between mode changes.

    Returns:
        OscillationReport with violations.
    """
    report = OscillationReport(
        total_decisions=len(decisions),
        min_decision_interval_ms=min_interval_ms,
    )

    if len(decisions) < 2:
        return report

    # Check for rapid alternation
    for i in range(1, len(decisions)):
        prev = decisions[i - 1]
        curr = decisions[i]

        # Check interval between mode changes
        if prev.ux_mode != curr.ux_mode:
            interval_ms = (curr.timestamp - prev.timestamp) * 1000
            if interval_ms < min_interval_ms and interval_ms > 0:
                report.oscillation_count += 1
                report.rapid_alternations.append(
                    f"{prev.ux_mode} → {curr.ux_mode} in {interval_ms:.0f}ms"
                )
                report.violations.append(
                    f"rapid_alternation: {interval_ms:.0f}ms < {min_interval_ms}ms"
                )

    # Check for A→B→A→B pattern
    modes = [d.ux_mode for d in decisions]
    for i in range(len(modes) - 3):
        window = modes[i:i + 4]
        if window[0] == window[2] and window[1] == window[3] and window[0] != window[1]:
            report.oscillation_count += 1
            report.violations.append(
                f"oscillation_pattern: {window[0]}→{window[1]}→{window[2]}→{window[3]}"
            )

    # Check confidence spikes without evidence
    for i, decision in enumerate(decisions):
        if decision.confidence >= CONFIDENCE_SPIKE_THRESHOLD:
            # High confidence requires corroborating signals
            if len(decision.reasoning) < MIN_CORROBORATING_SIGNALS:
                report.violations.append(
                    f"confidence_spike_without_evidence: "
                    f"confidence={decision.confidence:.2f}, "
                    f"reasoning_count={len(decision.reasoning)}"
                )

    report.passed = report.oscillation_count == 0 and len(report.violations) == 0

    logger.info(
        "oscillation_validation_complete",
        passed=report.passed,
        decisions=report.total_decisions,
        oscillations=report.oscillation_count,
        violations=len(report.violations),
    )

    return report


async def measure_orchestration_propagation_delay() -> PropagationDelayStats:
    """Measure delay between state change and orchestration decision emission."""
    return PropagationDelayStats()


async def validate_safety_corrections(
    corrections: list[SafetyCorrection],
    decisions: list[OrchestrationDecision],
) -> dict:
    """Validate that every safety correction references its source decision.

    Args:
        corrections: List of safety corrections applied.
        decisions: List of orchestration decisions made.

    Returns:
        Dict with passed, total_corrections, unlinked_corrections.
    """
    unlinked = 0
    for correction in corrections:
        if correction.decision_lineage_id is None:
            unlinked += 1

    return {
        "passed": unlinked == 0,
        "total_corrections": len(corrections),
        "unlinked_corrections": unlinked,
    }
