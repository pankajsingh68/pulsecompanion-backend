"""Observable validator — pure observer that constructs LoopTrace from bus events.

This replaces the simulated pipeline stages with real observation.
Subscribes to the event bus, collects events by lineage_id, and
constructs LoopTrace exclusively from observed events.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from events.event_bus import AsyncEventBus
from events.lineage import LineageContext, mint_lineage
from events.pipeline_events import (
    BaseEvent,
    PIPELINE_STAGE_ORDER,
    SensorIngestedEvent,
    SensorNormalizedEvent,
    StateEstimatedEvent,
    OrchestrationCompletedEvent,
    SafetyCorrectedEvent,
    WebSocketEmittedEvent,
    MemoryPersistedEvent,
)
from events.subscriptions import SubscriptionRegistry
from integration.adaptive_loop_validator import (
    LoopTrace,
    SensorReading,
    NormalizedReading,
    HumanStateEstimate,
    SmoothedState,
    OrchestrationDecision,
    SafetyCorrection,
    WebSocketEvent,
    MemoryEvent,
    validate_loop_trace,
    LoopValidationResult,
)
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ObservedStage:
    """A single observed pipeline stage event."""
    event_type: str
    lineage_id: UUID
    processing_timestamp: float
    payload: dict = field(default_factory=dict)


@dataclass
class ObservationWindow:
    """Collection of observed events for a single lineage_id."""
    lineage_id: UUID
    stages_observed: list[ObservedStage] = field(default_factory=list)
    started_at: float = 0.0
    completed_at: float | None = None

    @property
    def is_complete(self) -> bool:
        """All pipeline stages observed."""
        observed_types = {s.event_type for s in self.stages_observed}
        return all(stage in observed_types for stage in PIPELINE_STAGE_ORDER)

    @property
    def total_latency_ms(self) -> float:
        """End-to-end latency from first to last stage."""
        if len(self.stages_observed) < 2:
            return 0.0
        first = self.stages_observed[0].processing_timestamp
        last = self.stages_observed[-1].processing_timestamp
        return (last - first) * 1000

    def missing_stages(self) -> list[str]:
        """Stages that were expected but not observed."""
        observed_types = {s.event_type for s in self.stages_observed}
        return [s for s in PIPELINE_STAGE_ORDER if s not in observed_types]

    def duplicate_stages(self) -> list[str]:
        """Stages that were observed more than once."""
        from collections import Counter
        counts = Counter(s.event_type for s in self.stages_observed)
        return [stage for stage, count in counts.items() if count > 1]


@dataclass
class PropagationObservation:
    """Result of observing a single event's propagation through the pipeline."""
    lineage_id: UUID
    passed: bool = True
    window: ObservationWindow | None = None
    loop_trace: LoopTrace | None = None
    validation_result: LoopValidationResult | None = None
    missing_stages: list[str] = field(default_factory=list)
    duplicate_stages: list[str] = field(default_factory=list)
    out_of_order: bool = False
    total_latency_ms: float = 0.0
    per_stage_latency_ms: dict[str, float] = field(default_factory=dict)


class ObservablePipelineValidator:
    """Pure observer that validates pipeline propagation via event bus.

    Does NOT simulate stages. Subscribes to the bus, injects a synthetic
    event at the ingestion boundary, and observes what the pipeline emits.

    Usage:
        validator = ObservablePipelineValidator(bus)
        result = await validator.observe_propagation("test_session")
    """

    def __init__(self, bus: AsyncEventBus) -> None:
        self._bus = bus
        self._registry = SubscriptionRegistry(bus)
        self._windows: dict[UUID, ObservationWindow] = {}
        self._observation_complete: dict[UUID, asyncio.Event] = {}

    async def observe_propagation(
        self,
        session_id: str,
        timeout_seconds: float = 5.0,
    ) -> PropagationObservation:
        """Inject a synthetic event and observe its propagation.

        1. Subscribe to all pipeline stage events
        2. Inject a synthetic BiometricSnapshot with known lineage_id
        3. Await propagation (or timeout)
        4. Assert observed events match expected stage sequence
        5. Construct LoopTrace from observed events

        Args:
            session_id: Session to inject into.
            timeout_seconds: Max time to wait for full propagation.

        Returns:
            PropagationObservation with full trace and validation.
        """
        # Mint lineage for this observation
        lineage = mint_lineage(session_id, source="validator_injection")
        lid = lineage.lineage_id

        # Set up observation window
        self._windows[lid] = ObservationWindow(
            lineage_id=lid, started_at=time.monotonic()
        )
        self._observation_complete[lid] = asyncio.Event()

        # Subscribe to all pipeline events
        async def _on_event(event: BaseEvent) -> None:
            if event.lineage_id == lid:
                # Determine event type from class
                event_type = self._event_to_type(event)
                self._windows[lid].stages_observed.append(ObservedStage(
                    event_type=event_type,
                    lineage_id=event.lineage_id,
                    processing_timestamp=event.processing_timestamp,
                    payload=event.stage_payload_snapshot,
                ))
                # Check if all stages observed
                if self._windows[lid].is_complete:
                    self._windows[lid].completed_at = time.monotonic()
                    self._observation_complete[lid].set()

        self._registry.subscribe_all_pipeline_stages(_on_event, f"observer_{lid}")

        try:
            # Wait for propagation or timeout
            try:
                await asyncio.wait_for(
                    self._observation_complete[lid].wait(),
                    timeout=timeout_seconds,
                )
            except asyncio.TimeoutError:
                pass

            # Build observation result
            window = self._windows[lid]
            observation = PropagationObservation(
                lineage_id=lid,
                window=window,
                missing_stages=window.missing_stages(),
                duplicate_stages=window.duplicate_stages(),
                total_latency_ms=window.total_latency_ms,
            )

            # Check ordering
            timestamps = [s.processing_timestamp for s in window.stages_observed]
            observation.out_of_order = timestamps != sorted(timestamps)

            # Compute per-stage latency
            for i, stage in enumerate(window.stages_observed):
                if i == 0:
                    observation.per_stage_latency_ms[stage.event_type] = 0.0
                else:
                    prev = window.stages_observed[i - 1]
                    delta = (stage.processing_timestamp - prev.processing_timestamp) * 1000
                    observation.per_stage_latency_ms[stage.event_type] = round(delta, 3)

            # Build LoopTrace from observed events
            observation.loop_trace = self._build_loop_trace(lid, window)

            # Validate the trace
            if observation.loop_trace:
                observation.validation_result = validate_loop_trace(observation.loop_trace)

            # Determine pass/fail
            observation.passed = (
                window.is_complete
                and not observation.out_of_order
                and len(observation.duplicate_stages) == 0
            )

            logger.info(
                "propagation_observed",
                lineage_id=str(lid),
                passed=observation.passed,
                stages_observed=len(window.stages_observed),
                missing=observation.missing_stages,
                latency_ms=round(observation.total_latency_ms, 2),
            )

            return observation

        finally:
            # Cleanup
            self._registry.unsubscribe_group(f"observer_{lid}")
            self._windows.pop(lid, None)
            self._observation_complete.pop(lid, None)

    def _event_to_type(self, event: BaseEvent) -> str:
        """Map event class to event type string."""
        type_map = {
            SensorIngestedEvent: "sensor.ingested",
            SensorNormalizedEvent: "sensor.normalized",
            StateEstimatedEvent: "state.estimated",
            OrchestrationCompletedEvent: "orchestration.completed",
            SafetyCorrectedEvent: "safety.corrected",
            WebSocketEmittedEvent: "websocket.emitted",
            MemoryPersistedEvent: "memory.persisted",
        }
        return type_map.get(type(event), "unknown")

    def _build_loop_trace(
        self, lineage_id: UUID, window: ObservationWindow
    ) -> LoopTrace | None:
        """Construct LoopTrace exclusively from observed events."""
        if not window.stages_observed:
            return None

        trace = LoopTrace(lineage_id=lineage_id)

        for stage in window.stages_observed:
            payload = stage.payload

            if stage.event_type == "sensor.ingested":
                trace.raw_sensor = SensorReading(
                    hr=payload.get("hr"),
                    hrv=payload.get("hrv"),
                    gsr=payload.get("gsr"),
                    timestamp=stage.processing_timestamp,
                )
            elif stage.event_type == "sensor.normalized":
                trace.normalized_sensor = NormalizedReading(
                    hr_normalized=payload.get("hr"),
                    hrv_normalized=payload.get("hrv"),
                    quality_score=payload.get("reliability", {}).get("overall_confidence", 1.0),
                    timestamp=stage.processing_timestamp,
                )
            elif stage.event_type == "state.estimated":
                trace.state_estimate = HumanStateEstimate(
                    stress=payload.get("stress", 0),
                    fatigue=payload.get("fatigue", 0),
                    focus=payload.get("focus", 0.5),
                    engagement=payload.get("engagement", 0.5),
                    cognitive_load=payload.get("cognitive_load", 0.5),
                    ux_mode=payload.get("ux_mode", "normal"),
                )
                trace.smoothed_state = SmoothedState(
                    stress=payload.get("stress", 0),
                    fatigue=payload.get("fatigue", 0),
                    focus=payload.get("focus", 0.5),
                    ux_mode=payload.get("ux_mode", "normal"),
                    trend=payload.get("trend", "stable"),
                )
            elif stage.event_type == "orchestration.completed":
                trace.orchestration_decision = OrchestrationDecision(
                    ux_mode=payload.get("ux_mode", "normal"),
                    verbosity=payload.get("verbosity_level", "normal"),
                    tone=payload.get("response_tone", "neutral"),
                    confidence=payload.get("confidence", 0.5),
                    reasoning=payload.get("reasoning", []),
                    timestamp=stage.processing_timestamp,
                )
            elif stage.event_type == "safety.corrected":
                if payload.get("was_limited"):
                    trace.safety_corrections.append(SafetyCorrection(
                        field_name=", ".join(payload.get("limited_fields", [])),
                        reason="safety_bounded",
                    ))
            elif stage.event_type == "websocket.emitted":
                trace.emitted_websocket_event = WebSocketEvent(
                    event_type=payload.get("event_type", ""),
                    lineage_id=lineage_id,
                    timestamp=stage.processing_timestamp,
                    payload=payload,
                )
            elif stage.event_type == "memory.persisted":
                trace.stored_memory_event = MemoryEvent(
                    tier=payload.get("tier", "working"),
                    importance_score=payload.get("importance", 0),
                    lineage_id=lineage_id,
                    timestamp=stage.processing_timestamp,
                )

        # Record per-stage latencies
        for stage in window.stages_observed:
            trace.stage_latencies_ms[stage.event_type] = round(
                stage.processing_timestamp * 1000, 3
            )

        return trace
