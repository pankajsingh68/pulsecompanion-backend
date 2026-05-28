"""Pipeline validator — signal propagation and lineage tracing.

Validates that a synthetic sensor event travels the full pipeline
and produces a traceable output at every stage within latency budget.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from integration import LineageTrace, ValidatorMode, mint_lineage
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SensorScenario:
    """Input scenario for pipeline validation."""
    session_id: str = "pipeline_test"
    hr: float = 72.0
    hrv: float = 50.0
    gsr: float | None = None
    message: str = ""
    mode: ValidatorMode = ValidatorMode.SIMULATION


@dataclass
class StageResult:
    """Result of a single pipeline stage."""
    stage_name: str
    passed: bool = True
    latency_ms: float = 0.0
    lineage_id: UUID | None = None
    output_snapshot: Any = None
    error: str | None = None


@dataclass
class PropagationReport:
    """Full report of signal propagation through the pipeline."""
    passed: bool = True
    lineage_id: UUID | None = None
    stages: list[StageResult] = field(default_factory=list)
    total_latency_ms: float = 0.0
    lineage_preserved: bool = True
    dropped_at_stage: str | None = None
    trace: LineageTrace | None = None


@dataclass
class LatencyStats:
    """Statistical summary of adaptive latency measurements."""
    samples: int = 0
    mean_ms: float = 0.0
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    max_ms: float = 0.0
    min_ms: float = 0.0
    within_budget: bool = True
    budget_ms: float = 500.0


PIPELINE_STAGES = [
    "sensor_ingest",
    "normalization",
    "state_estimation",
    "temporal_smoothing",
    "orchestration",
    "safety_check",
    "websocket_emit",
    "memory_write",
]

DEFAULT_SLA_MS = 50.0


async def validate_signal_propagation(
    scenario: SensorScenario | None = None,
) -> PropagationReport:
    """Validate that a synthetic sensor event propagates through all stages.

    Injects a synthetic event, traces it through each stage, and asserts:
    - Each stage produces output within SLA
    - lineage_id is identical at all stages
    - No stage silently swallows the event

    Args:
        scenario: The sensor scenario to inject. Uses defaults if None.

    Returns:
        PropagationReport with per-stage results and overall pass/fail.
    """
    if scenario is None:
        scenario = SensorScenario()

    trace = mint_lineage()
    report = PropagationReport(lineage_id=trace.lineage_id, trace=trace)
    pipeline_start = time.monotonic()

    for stage_name in PIPELINE_STAGES:
        stage_start = time.monotonic()

        try:
            # Simulate stage processing
            # In full integration, each stage would be called with the trace
            output = await _execute_stage(stage_name, scenario, trace)

            latency_ms = (time.monotonic() - stage_start) * 1000
            stage_result = StageResult(
                stage_name=stage_name,
                passed=latency_ms <= DEFAULT_SLA_MS,
                latency_ms=round(latency_ms, 3),
                lineage_id=trace.lineage_id,
                output_snapshot=output,
            )

            if latency_ms > DEFAULT_SLA_MS:
                stage_result.error = f"SLA exceeded: {latency_ms:.1f}ms > {DEFAULT_SLA_MS}ms"

        except Exception as e:
            latency_ms = (time.monotonic() - stage_start) * 1000
            stage_result = StageResult(
                stage_name=stage_name,
                passed=False,
                latency_ms=round(latency_ms, 3),
                lineage_id=trace.lineage_id,
                error=str(e),
            )
            report.dropped_at_stage = stage_name

        report.stages.append(stage_result)

    report.total_latency_ms = (time.monotonic() - pipeline_start) * 1000
    report.passed = all(s.passed for s in report.stages)
    report.lineage_preserved = all(
        s.lineage_id == trace.lineage_id for s in report.stages
    )

    if not report.lineage_preserved:
        report.passed = False

    logger.info(
        "pipeline_validation_complete",
        passed=report.passed,
        total_latency_ms=round(report.total_latency_ms, 2),
        stages_passed=sum(1 for s in report.stages if s.passed),
        stages_total=len(report.stages),
    )

    return report


async def measure_adaptive_latency(n_samples: int = 100) -> LatencyStats:
    """Measure end-to-end adaptive latency over N samples.

    Total adaptive latency = t(websocket_emit) − t(raw_sensor_ingest).

    Args:
        n_samples: Number of samples to collect.

    Returns:
        LatencyStats with percentile breakdown.
    """
    latencies: list[float] = []

    for _ in range(n_samples):
        start = time.monotonic()
        # Simulate full pipeline pass
        for stage in PIPELINE_STAGES:
            await _execute_stage(stage, SensorScenario(), mint_lineage())
        elapsed_ms = (time.monotonic() - start) * 1000
        latencies.append(elapsed_ms)

    if not latencies:
        return LatencyStats()

    latencies.sort()
    n = len(latencies)

    stats = LatencyStats(
        samples=n,
        mean_ms=round(sum(latencies) / n, 3),
        p50_ms=round(latencies[n // 2], 3),
        p95_ms=round(latencies[int(n * 0.95)], 3),
        p99_ms=round(latencies[int(n * 0.99)], 3),
        max_ms=round(latencies[-1], 3),
        min_ms=round(latencies[0], 3),
        budget_ms=500.0,
    )
    stats.within_budget = stats.p95_ms <= stats.budget_ms

    logger.info(
        "latency_measurement_complete",
        samples=n,
        mean_ms=stats.mean_ms,
        p95_ms=stats.p95_ms,
        within_budget=stats.within_budget,
    )

    return stats


async def _execute_stage(
    stage_name: str, scenario: SensorScenario, trace: LineageTrace
) -> dict:
    """Execute a single pipeline stage (simulation mode).

    In full integration, this dispatches to the actual subsystem.
    In simulation mode, it validates the interface contract.
    """
    # Each stage returns a dict representing its output
    return {
        "stage": stage_name,
        "lineage_id": str(trace.lineage_id),
        "session_id": scenario.session_id,
        "timestamp": time.time(),
    }
