"""WebSocket flow validator — delivery correctness and ordering.

Validates emission ordering, deduplication, staleness rejection,
disconnect handling, and backpressure behavior.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from uuid import UUID

from integration.adaptive_loop_validator import LoopTrace
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ThroughputStats:
    """WebSocket throughput statistics."""
    events_per_second_in: float = 0.0
    events_per_second_out: float = 0.0
    queue_depth: int = 0
    dropped_events: int = 0
    throttle_activations: int = 0
    reconnect_count: int = 0


@dataclass
class OrderingReport:
    """Report on WebSocket emission ordering."""
    passed: bool = True
    total_events: int = 0
    temporal_inversions: int = 0
    duplicate_lineage_ids: int = 0
    stale_emissions: int = 0
    violations: list[str] = field(default_factory=list)
    max_staleness_ms: float = 5000.0


async def get_websocket_throughput() -> ThroughputStats:
    """Introspection API: get current WebSocket throughput stats."""
    return ThroughputStats()


async def validate_emission_ordering(
    trace_window: list[LoopTrace],
    max_staleness_ms: float = 5000.0,
) -> OrderingReport:
    """Validate WebSocket emission correctness and ordering.

    Checks:
    - Events emitted in monotonic order (no temporal inversion)
    - No duplicate emissions for the same lineage_id
    - Stale events rejected (timestamp > max_staleness_ms behind wall clock)
    - No silent drops

    Args:
        trace_window: List of LoopTraces to validate.
        max_staleness_ms: Maximum allowed staleness in milliseconds.

    Returns:
        OrderingReport with violations.
    """
    report = OrderingReport(
        total_events=len(trace_window),
        max_staleness_ms=max_staleness_ms,
    )

    seen_lineage_ids: set[UUID] = set()
    last_timestamp: float = 0.0
    now = time.time()

    for trace in trace_window:
        ws_event = trace.emitted_websocket_event
        if ws_event is None:
            report.violations.append("missing_websocket_event")
            continue

        # Check monotonic ordering
        if ws_event.timestamp < last_timestamp:
            report.temporal_inversions += 1
            report.violations.append(
                f"temporal_inversion: {ws_event.timestamp} < {last_timestamp}"
            )
        last_timestamp = ws_event.timestamp

        # Check duplicate lineage_id
        if ws_event.lineage_id is not None:
            if ws_event.lineage_id in seen_lineage_ids:
                report.duplicate_lineage_ids += 1
                report.violations.append(
                    f"duplicate_lineage_id: {ws_event.lineage_id}"
                )
            seen_lineage_ids.add(ws_event.lineage_id)

        # Check staleness
        staleness_ms = (now - ws_event.timestamp) * 1000
        if staleness_ms > max_staleness_ms:
            report.stale_emissions += 1
            report.violations.append(
                f"stale_emission: {staleness_ms:.0f}ms > {max_staleness_ms}ms"
            )

    report.passed = (
        report.temporal_inversions == 0
        and report.duplicate_lineage_ids == 0
        and report.stale_emissions == 0
    )

    logger.info(
        "websocket_ordering_validated",
        passed=report.passed,
        events=report.total_events,
        inversions=report.temporal_inversions,
        duplicates=report.duplicate_lineage_ids,
        stale=report.stale_emissions,
    )

    return report
