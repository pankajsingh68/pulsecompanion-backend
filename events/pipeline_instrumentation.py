"""Pipeline instrumentation — emits events at each stage boundary.

This module provides the emit_* functions called by the production pipeline
at each explicit stage boundary. The pipeline becomes self-describing.

No validator touches this. Validators subscribe to the event bus and observe.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from events.lineage import LineageContext
from events.pipeline_events import (
    DegradedModeChangedEvent,
    MemoryPersistedEvent,
    OrchestrationCompletedEvent,
    SafetyCorrectedEvent,
    SensorIngestedEvent,
    SensorNormalizedEvent,
    StateEstimatedEvent,
    WebSocketEmittedEvent,
)
from utils.logger import get_logger

if TYPE_CHECKING:
    from events.event_bus import AsyncEventBus

logger = get_logger(__name__)


class PipelineInstrumentation:
    """Instruments the production pipeline with event emissions.

    Each method corresponds to a pipeline stage boundary.
    Call these at the appropriate point in the production code.
    """

    def __init__(self, bus: "AsyncEventBus") -> None:
        self._bus = bus

    async def emit_sensor_ingested(
        self, lineage: LineageContext, hr: float | None, hrv: float | None,
        gsr: float | None = None, source: str = "manual", quality: float = 1.0,
    ) -> None:
        """Emit at raw sensor ingestion boundary."""
        event = SensorIngestedEvent(
            lineage_id=lineage.lineage_id,
            session_id=lineage.session_id,
            hr=hr, hrv=hrv, gsr=gsr,
            source=source, quality=quality,
            stage_payload_snapshot={"hr": hr, "hrv": hrv, "gsr": gsr},
        )
        await self._bus.emit("sensor.ingested", event)

    async def emit_sensor_normalized(
        self, lineage: LineageContext, hr_normalized: float | None,
        hrv_normalized: float | None, reliability_report: dict,
    ) -> None:
        """Emit after sensor normalization."""
        event = SensorNormalizedEvent(
            lineage_id=lineage.lineage_id,
            session_id=lineage.session_id,
            hr_normalized=hr_normalized,
            hrv_normalized=hrv_normalized,
            reliability_report=reliability_report,
            stage_payload_snapshot={
                "hr": hr_normalized, "hrv": hrv_normalized,
                "reliability": reliability_report,
            },
        )
        await self._bus.emit("sensor.normalized", event)

    async def emit_state_estimated(
        self, lineage: LineageContext, state: dict,
    ) -> None:
        """Emit after HumanStateEngine produces state."""
        event = StateEstimatedEvent(
            lineage_id=lineage.lineage_id,
            session_id=lineage.session_id,
            stress=state.get("stress", 0),
            fatigue=state.get("fatigue", 0),
            focus=state.get("focus", 0.5),
            engagement=state.get("engagement", 0.5),
            cognitive_load=state.get("cognitive_load", 0.5),
            ux_mode=state.get("ux_mode", "normal"),
            confidence=state.get("inference_confidence", 0.5),
            trend=state.get("trend", "stable"),
            stage_payload_snapshot=state,
        )
        await self._bus.emit("state.estimated", event)

    async def emit_orchestration_completed(
        self, lineage: LineageContext, strategy: dict,
    ) -> None:
        """Emit after UXOrchestrator produces strategy."""
        event = OrchestrationCompletedEvent(
            lineage_id=lineage.lineage_id,
            session_id=lineage.session_id,
            ux_mode=strategy.get("ux_mode", "normal"),
            verbosity_level=strategy.get("verbosity_level", "normal"),
            response_tone=strategy.get("response_tone", "neutral"),
            suggest_break=strategy.get("suggest_break", False),
            suppress_notifications=strategy.get("suppress_notifications", False),
            orchestration_confidence=strategy.get("confidence", 0.5),
            reasoning=strategy.get("reasoning", []),
            stage_payload_snapshot=strategy,
        )
        await self._bus.emit("orchestration.completed", event)

    async def emit_safety_corrected(
        self, lineage: LineageContext, was_limited: bool,
        limited_fields: list[str], original_mode: str, corrected_mode: str,
        reasoning: str = "",
    ) -> None:
        """Emit after safety layer applies corrections."""
        event = SafetyCorrectedEvent(
            lineage_id=lineage.lineage_id,
            session_id=lineage.session_id,
            was_limited=was_limited,
            limited_fields=limited_fields,
            original_mode=original_mode,
            corrected_mode=corrected_mode,
            guard_reasoning=reasoning,
            stage_payload_snapshot={
                "was_limited": was_limited,
                "limited_fields": limited_fields,
            },
        )
        await self._bus.emit("safety.corrected", event)

    async def emit_websocket_emitted(
        self, lineage: LineageContext, event_type: str,
        payload_size: int, success: bool = True,
    ) -> None:
        """Emit after WebSocket payload dispatch."""
        event = WebSocketEmittedEvent(
            lineage_id=lineage.lineage_id,
            session_id=lineage.session_id,
            event_type=event_type,
            payload_size_bytes=payload_size,
            target_session=lineage.session_id,
            delivery_success=success,
            stage_payload_snapshot={
                "event_type": event_type,
                "size": payload_size,
                "success": success,
            },
        )
        await self._bus.emit("websocket.emitted", event)

    async def emit_memory_persisted(
        self, lineage: LineageContext, tier: str,
        importance_score: float, episode_type: str | None = None,
        collection_name: str = "",
    ) -> None:
        """Emit after memory record is written."""
        event = MemoryPersistedEvent(
            lineage_id=lineage.lineage_id,
            session_id=lineage.session_id,
            tier=tier,
            importance_score=importance_score,
            episode_type=episode_type,
            collection_name=collection_name,
            stage_payload_snapshot={
                "tier": tier,
                "importance": importance_score,
                "episode_type": episode_type,
            },
        )
        await self._bus.emit("memory.persisted", event)

    async def emit_degraded_mode_changed(
        self, lineage: LineageContext, previous_mode: str,
        new_mode: str, reason: str, affected: list[str],
    ) -> None:
        """Emit when system enters/exits degraded mode."""
        event = DegradedModeChangedEvent(
            lineage_id=lineage.lineage_id,
            session_id=lineage.session_id,
            previous_mode=previous_mode,
            new_mode=new_mode,
            reason=reason,
            affected_subsystems=affected,
            stage_payload_snapshot={
                "previous": previous_mode,
                "new": new_mode,
                "reason": reason,
            },
        )
        await self._bus.emit("degraded_mode.changed", event)
