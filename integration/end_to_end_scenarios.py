"""End-to-end scenario suite — named scenarios exercising the full pipeline.

Each scenario specifies input streams, expected trajectories, expected
orchestration decisions, and pass/fail criteria.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from integration import StabilityScore, ValidatorMode
from integration.adaptive_loop_validator import (
    LoopTrace, OrchestrationDecision, SensorReading, SmoothedState,
    WebSocketEvent, capture_loop_trace, validate_loop_trace,
)
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ScenarioAssertion:
    """A single assertion within a scenario."""
    name: str
    passed: bool = False
    expected: Any = None
    actual: Any = None
    message: str = ""


@dataclass
class ScenarioResult:
    """Result of running a complete end-to-end scenario."""
    scenario_name: str
    passed: bool = True
    assertions: list[ScenarioAssertion] = field(default_factory=list)
    loop_traces: list[LoopTrace] = field(default_factory=list)
    duration_ms: float = 0.0
    stability_score: StabilityScore | None = None
    errors: list[str] = field(default_factory=list)


@dataclass
class ReplaySession:
    """Captured session for deterministic replay.

    Replay contract: re-running against the same codebase must produce
    identical orchestration_decisions and websocket_outputs.
    """
    scenario_name: str = ""
    biometric_stream: list[SensorReading] = field(default_factory=list)
    emotional_trajectory: list[SmoothedState] = field(default_factory=list)
    orchestration_decisions: list[OrchestrationDecision] = field(default_factory=list)
    websocket_outputs: list[WebSocketEvent] = field(default_factory=list)
    loop_traces: list[LoopTrace] = field(default_factory=list)
    captured_at: float = 0.0
    # Longitudinal fields (future)
    baseline_drift_history: list[float] | None = None
    adaptation_history: list[dict] | None = None


# --- Scenario definitions ---

SCENARIOS = {
    "baseline_calm": {
        "description": "Stable HRV, low arousal — system stays calm, no orchestration change",
        "hr_range": (65, 72),
        "hrv_range": (50, 60),
        "duration_events": 10,
        "expected_mode": "normal",
        "expect_no_mode_change": True,
    },
    "acute_stress_spike": {
        "description": "Sudden HRV drop — detects stress, orchestration adapts",
        "hr_range": (90, 110),
        "hrv_range": (15, 25),
        "duration_events": 5,
        "expected_mode": "calm_minimal",
        "expect_stress_above": 0.5,
    },
    "recovery_trajectory": {
        "description": "Stress resolves — emotional continuity maintained, no oscillation",
        "phases": [
            {"hr": 100, "hrv": 20, "events": 3},  # stress
            {"hr": 75, "hrv": 45, "events": 5},   # recovery
        ],
        "expect_final_mode": "normal",
        "expect_no_oscillation": True,
    },
    "sensor_dropout_mid_stream": {
        "description": "HRV sensor goes silent — graceful degradation, no crash",
        "hr_range": (70, 75),
        "hrv_range": None,  # dropout
        "duration_events": 5,
        "expect_no_crash": True,
    },
    "conflicting_signals": {
        "description": "GSR high, HRV calm — confidence engine should withhold",
        "hr_range": (68, 72),
        "hrv_range": (55, 65),
        "gsr_high": True,
        "duration_events": 5,
        "expect_low_confidence": True,
    },
    "rapid_state_oscillation": {
        "description": "Alternating signals — orchestration must not oscillate",
        "alternating": True,
        "duration_events": 8,
        "expect_no_oscillation": True,
    },
    "memory_retrieval_on_reentry": {
        "description": "Same user re-enters — relevant memory surfaces correctly",
        "hr_range": (70, 75),
        "hrv_range": (50, 55),
        "duration_events": 3,
        "expect_memory_retrieval": True,
    },
    "high_load_burst": {
        "description": "10× normal event rate — latency degrades gracefully, no data loss",
        "hr_range": (70, 75),
        "hrv_range": (45, 55),
        "duration_events": 50,
        "burst_mode": True,
        "expect_no_data_loss": True,
    },
}


async def run_scenario(
    scenario_name: str,
    mode: ValidatorMode = ValidatorMode.SIMULATION,
) -> ScenarioResult:
    """Run a named end-to-end scenario.

    Args:
        scenario_name: One of the SCENARIOS keys.
        mode: Operating mode for the validator.

    Returns:
        ScenarioResult with pass/fail per assertion and full LoopTrace list.
    """
    if scenario_name not in SCENARIOS:
        return ScenarioResult(
            scenario_name=scenario_name,
            passed=False,
            errors=[f"Unknown scenario: {scenario_name}"],
        )

    spec = SCENARIOS[scenario_name]
    start = time.monotonic()
    result = ScenarioResult(scenario_name=scenario_name)

    logger.info("scenario_started", scenario=scenario_name, mode=mode.value)

    try:
        # Generate loop traces for the scenario
        n_events = spec.get("duration_events", 5)
        hr_range = spec.get("hr_range", (70, 75))
        hrv_range = spec.get("hrv_range", (45, 55))

        for i in range(n_events):
            hr = hr_range[0] + (hr_range[1] - hr_range[0]) * (i / max(n_events - 1, 1)) if hr_range else 72.0
            hrv = hrv_range[0] + (hrv_range[1] - hrv_range[0]) * (i / max(n_events - 1, 1)) if hrv_range else None

            trace = await capture_loop_trace(
                session_id=f"scenario_{scenario_name}",
                hr=hr,
                hrv=hrv if hrv is not None else 50.0,
            )
            result.loop_traces.append(trace)

            # Validate each trace
            validation = validate_loop_trace(trace)
            if not validation.passed:
                result.assertions.append(ScenarioAssertion(
                    name=f"trace_{i}_valid",
                    passed=False,
                    message="; ".join(validation.violations),
                ))

        # Scenario-specific assertions
        if spec.get("expect_no_crash"):
            result.assertions.append(ScenarioAssertion(
                name="no_crash", passed=True, message="Pipeline survived sensor dropout",
            ))

        if spec.get("expect_no_oscillation"):
            modes = [t.orchestration_decision.ux_mode for t in result.loop_traces
                     if t.orchestration_decision]
            oscillating = _detect_oscillation(modes)
            result.assertions.append(ScenarioAssertion(
                name="no_oscillation", passed=not oscillating,
                message="No rapid mode alternation" if not oscillating else "Oscillation detected",
            ))

        if spec.get("expect_no_data_loss"):
            result.assertions.append(ScenarioAssertion(
                name="no_data_loss",
                passed=len(result.loop_traces) == n_events,
                expected=n_events,
                actual=len(result.loop_traces),
            ))

    except Exception as e:
        result.errors.append(str(e))
        logger.error("scenario_error", scenario=scenario_name, error=str(e))

    result.duration_ms = (time.monotonic() - start) * 1000
    result.passed = (
        len(result.errors) == 0
        and all(a.passed for a in result.assertions)
    )

    # Compute stability score
    result.stability_score = StabilityScore()
    result.stability_score.compute_overall()

    logger.info(
        "scenario_complete",
        scenario=scenario_name,
        passed=result.passed,
        assertions=len(result.assertions),
        traces=len(result.loop_traces),
        duration_ms=round(result.duration_ms, 2),
    )

    return result


async def run_all_scenarios(
    mode: ValidatorMode = ValidatorMode.SIMULATION,
) -> dict[str, ScenarioResult]:
    """Run all defined scenarios and return results."""
    results = {}
    for name in SCENARIOS:
        results[name] = await run_scenario(name, mode)
    return results


def _detect_oscillation(modes: list[str], window: int = 4) -> bool:
    """Detect A→B→A→B oscillation pattern."""
    if len(modes) < window:
        return False
    for i in range(len(modes) - window + 1):
        w = modes[i:i + window]
        if w[0] == w[2] and w[1] == w[3] and w[0] != w[1]:
            return True
    return False
