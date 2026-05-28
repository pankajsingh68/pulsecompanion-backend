"""LoopTrace assembler — reconstructs full adaptive cycles from bus events.

Assembles LoopTrace incrementally from observed events, keyed by lineage_id.
Preserves monotonic ordering, detects missing/duplicate stages.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable
from uuid import UUID

from events.event_bus import AsyncEventBus
from events.pipeline_events import (
    BaseEvent,
    MemoryPersistedEvent,
    OrchestrationCompletedEvent,
    PIPELINE_STAGE_ORDER,
    SafetyCorrectedEvent,
    SensorIngestedEvent,
    SensorNormalizedEvent,
    StateEstimatedEvent,
    WebSocketEmittedEvent,
)
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class LoopTrace:
    """Fully reconstructed adaptive cycle from real bus events.

    Open schema: nullable fields for future longitudinal extensions.
    """
    lineage_id: UUID | None = None
    raw_sensor: SensorIngestedEvent | None = None
    normalized_sensor: SensorNormalizedEvent | None = None
    state_estimate: StateEstimatedEvent | None = None
    orchestration_decision: OrchestrationCompletedEvent | None = None
    safety_correction: SafetyCorrectedEvent | None = None
    websocket_emission: WebSocketEmittedEvent | None = None
    memory_persistence: MemoryPersistedEvent | None = None
    stage_latencies_ms: dict[str, float] = field(default_factory=dict)
    completed: bool = False
    missing_stages: list[str] = field(default_factory=list)
    duplicate_stages: list[str] = field(default_factory=list)
    ordering_violations: list[str] = field(default_factory=list)
    started_at: float = 0.0
    completed_at: float | None = None
    # Future longitudinal fields
    baseline_drift: float | None = None
    adaptation_history: list[dict] | None = None
    emotional_continuity: float | None = None


# Map event type strings to LoopTrace field names
_STAGE_TO_FIELD = {
    "sensor.ingested": "raw_sensor",
    "sensor.normalized": "normalized_sensor",
    "state.estimated": "state_estimate",
    "orchestration.completed": "orchestration_decision",
    "safety.corrected": "safety_correction",
    "websocket.emitted": "websocket_emission",
    "memory.persisted": "memory_persistence",
}

_EVENT_CLASS_TO_TYPE = {
    SensorIngestedEvent: "sensor.ingested",
    SensorNormalizedEvent: "sensor.normalized",
    StateEstimatedEvent: "state.estimated",
    OrchestrationCompletedEvent: "orchestration.completed",
    SafetyCorrectedEvent: "safety.corrected",
    WebSocketEmittedEvent: "websocket.emitted",
    MemoryPersistedEvent: "memory.persisted",
}


class LoopTraceAssembler:
    """Assembles LoopTrace incrementally from observed bus events.

    Keyed by lineage_id. Detects missing stages, duplicates,
    and ordering violations.
    """

    def __init__(self, on_complete: Callable[[LoopTrace], Any] | None = None) -> None:
        self._active_traces: dict[UUID, LoopTrace] = {}
        self._stage_timestamps: dict[UUID, list[tuple[str, float]]] = {}
        self._on_complete = on_complete

    async def on_event(self, event: BaseEvent) -> None:
        """Process a single bus event into the appropriate LoopTrace."""
        lid = event.lineage_id
        event_type = _EVENT_CLASS_TO_TYPE.get(type(event))
        if event_type is None:
            return

        # Get or create trace
        if lid not in self._active_traces:
            self._active_traces[lid] = LoopTrace(
                lineage_id=lid,
                started_at=event.processing_timestamp,
            )
            self._stage_timestamps[lid] = []

        trace = self._active_traces[lid]
        field_name = _STAGE_TO_FIELD.get(event_type)

        if field_name is None:
            return

        # Detect duplicate stage emission
        if getattr(trace, field_name) is not None:
            trace.duplicate_stages.append(event_type)
        else:
            setattr(trace, field_name, event)

        # Record timestamp for latency computation
        self._stage_timestamps[lid].append(
            (event_type, event.processing_timestamp)
        )

        # Check completion
        self._check_completion(lid)

    def _check_completion(self, lid: UUID) -> None:
        """Check if all expected stages have been received."""
        trace = self._active_traces[lid]
        received = set()

        for stage, field_name in _STAGE_TO_FIELD.items():
            if getattr(trace, field_name) is not None:
                received.add(stage)

        missing = [s for s in PIPELINE_STAGE_ORDER if s not in received]
        trace.missing_stages = missing

        if not missing:
            trace.completed = True
            trace.completed_at = time.monotonic()
            self._compute_latencies(lid)
            self._check_ordering(lid)

            if self._on_complete:
                try:
                    self._on_complete(trace)
                except Exception as e:
                    logger.warning("looptrace_callback_error", error=str(e))

    def _compute_latencies(self, lid: UUID) -> None:
        """Compute inter-stage latencies from timestamps."""
        trace = self._active_traces[lid]
        timestamps = self._stage_timestamps.get(lid, [])

        if len(timestamps) < 2:
            return

        for i in range(1, len(timestamps)):
            prev_stage, prev_ts = timestamps[i - 1]
            curr_stage, curr_ts = timestamps[i]
            delta_ms = (curr_ts - prev_ts) * 1000
            trace.stage_latencies_ms[f"{prev_stage}→{curr_stage}"] = round(delta_ms, 3)

    def _check_ordering(self, lid: UUID) -> None:
        """Enforce monotonic ordering — flag violations."""
        trace = self._active_traces[lid]
        timestamps = self._stage_timestamps.get(lid, [])

        for i in range(1, len(timestamps)):
            prev_stage, prev_ts = timestamps[i - 1]
            curr_stage, curr_ts = timestamps[i]
            if curr_ts < prev_ts:
                trace.ordering_violations.append(
                    f"{prev_stage}({prev_ts:.6f}) → {curr_stage}({curr_ts:.6f})"
                )

    def get_trace(self, lineage_id: UUID) -> LoopTrace | None:
        """Get a trace by lineage_id."""
        return self._active_traces.get(lineage_id)

    def get_completed_traces(self) -> list[LoopTrace]:
        """Get all completed traces."""
        return [t for t in self._active_traces.values() if t.completed]

    def get_incomplete_traces(self) -> list[LoopTrace]:
        """Get all incomplete (partial) traces."""
        return [t for t in self._active_traces.values() if not t.completed]

    @property
    def active_count(self) -> int:
        return len(self._active_traces)

    @property
    def completed_count(self) -> int:
        return sum(1 for t in self._active_traces.values() if t.completed)


class TraceStore:
    """In-memory trace registry with eviction policy."""

    def __init__(self, max_completed: int = 100, max_active: int = 50) -> None:
        self._completed: list[LoopTrace] = []
        self._max_completed = max_completed
        self._max_active = max_active

    def store_completed(self, trace: LoopTrace) -> None:
        """Store a completed trace. Evicts oldest if at capacity."""
        self._completed.append(trace)
        if len(self._completed) > self._max_completed:
            self._completed.pop(0)

    def get_recent(self, n: int = 10) -> list[LoopTrace]:
        """Get N most recent completed traces."""
        return self._completed[-n:]

    def get_by_lineage(self, lineage_id: UUID) -> LoopTrace | None:
        """Find a trace by lineage_id."""
        for trace in reversed(self._completed):
            if trace.lineage_id == lineage_id:
                return trace
        return None

    def get_completion_rate(self) -> float:
        """Fraction of traces that completed successfully."""
        if not self._completed:
            return 0.0
        complete = sum(1 for t in self._completed if t.completed and not t.ordering_violations)
        return complete / len(self._completed)

    @property
    def count(self) -> int:
        return len(self._completed)
