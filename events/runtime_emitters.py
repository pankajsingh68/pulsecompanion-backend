"""Runtime-native event emitters — subsystem-local emission adapters.

Each subsystem owns and emits its own events directly.
InstrumentedIngestionPipeline becomes orchestration glue only.
Emission failure never crashes runtime. All emission is async-safe.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID

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
    from events.lineage import LineageContext

logger = get_logger(__name__)


async def _safe_emit(bus: "AsyncEventBus", event_type: str, event) -> None:
    """Async-safe emit wrapper — never crashes runtime."""
    try:
        await bus.emit(event_type, event)
    except Exception as e:
        logger.warning("runtime_emit_failed", event_type=event_type, error=str(e))


class OrchestrationEmitter:
    """Emits orchestration.completed from the orchestration subsystem."""

    def __init__(self, bus: "AsyncEventBus") -> None:
        self._bus = bus

    async def emit(self, lineage: "LineageContext", strategy_dict: dict) -> None:
        event = OrchestrationCompletedEvent(
            lineage_id=lineage.lineage_id,
            session_id=lineage.session_id,
            ux_mode=strategy_dict.get("ux_mode", "normal"),
            verbosity_level=strategy_dict.get("verbosity_level", "normal"),
            response_tone=strategy_dict.get("response_tone", "neutral"),
            suggest_break=strategy_dict.get("suggest_break", False),
            suppress_notifications=strategy_dict.get("suppress_notifications", False),
            orchestration_confidence=strategy_dict.get("confidence", 0.5),
            reasoning=strategy_dict.get("reasoning", []),
            stage_payload_snapshot=dict(strategy_dict),
        )
        await _safe_emit(self._bus, "orchestration.completed", event)


class SafetyEmitter:
    """Emits safety.corrected from the safety subsystem."""

    def __init__(self, bus: "AsyncEventBus") -> None:
        self._bus = bus

    async def emit(
        self, lineage: "LineageContext", was_limited: bool,
        limited_fields: list[str], original_mode: str,
        corrected_mode: str, reasoning: str = "",
    ) -> None:
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
                "original_mode": original_mode,
                "corrected_mode": corrected_mode,
            },
        )
        await _safe_emit(self._bus, "safety.corrected", event)


class WebSocketEmitter:
    """Emits websocket.emitted from the WebSocket manager."""

    def __init__(self, bus: "AsyncEventBus") -> None:
        self._bus = bus

    async def emit(
        self, lineage: "LineageContext", event_type: str,
        payload_size: int, success: bool = True,
    ) -> None:
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
        await _safe_emit(self._bus, "websocket.emitted", event)


class MemoryEmitter:
    """Emits memory.persisted from the memory subsystem."""

    def __init__(self, bus: "AsyncEventBus") -> None:
        self._bus = bus

    async def emit(
        self, lineage: "LineageContext", tier: str,
        importance_score: float, episode_type: str | None = None,
        collection_name: str = "",
    ) -> None:
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
        await _safe_emit(self._bus, "memory.persisted", event)


class DegradedModeEmitter:
    """Emits degraded_mode.changed from the degraded mode controller."""

    def __init__(self, bus: "AsyncEventBus") -> None:
        self._bus = bus

    async def emit(
        self, lineage: "LineageContext", previous_mode: str,
        new_mode: str, reason: str, affected: list[str],
    ) -> None:
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
                "affected": affected,
            },
        )
        await _safe_emit(self._bus, "degraded_mode.changed", event)


class SensorEmitter:
    """Emits sensor.ingested and sensor.normalized from sensor subsystem."""

    def __init__(self, bus: "AsyncEventBus") -> None:
        self._bus = bus

    async def emit_ingested(
        self, lineage: "LineageContext", hr: float | None,
        hrv: float | None, gsr: float | None = None,
        source: str = "manual", quality: float = 1.0,
    ) -> None:
        event = SensorIngestedEvent(
            lineage_id=lineage.lineage_id,
            session_id=lineage.session_id,
            hr=hr, hrv=hrv, gsr=gsr,
            source=source, quality=quality,
            stage_payload_snapshot={"hr": hr, "hrv": hrv, "gsr": gsr},
        )
        await _safe_emit(self._bus, "sensor.ingested", event)

    async def emit_normalized(
        self, lineage: "LineageContext", hr: float | None,
        hrv: float | None, reliability: dict,
    ) -> None:
        event = SensorNormalizedEvent(
            lineage_id=lineage.lineage_id,
            session_id=lineage.session_id,
            hr_normalized=hr, hrv_normalized=hrv,
            reliability_report=reliability,
            stage_payload_snapshot={"hr": hr, "hrv": hrv, "reliability": reliability},
        )
        await _safe_emit(self._bus, "sensor.normalized", event)


class StateEmitter:
    """Emits state.estimated from the human state engine."""

    def __init__(self, bus: "AsyncEventBus") -> None:
        self._bus = bus

    async def emit(self, lineage: "LineageContext", state_dict: dict) -> None:
        event = StateEstimatedEvent(
            lineage_id=lineage.lineage_id,
            session_id=lineage.session_id,
            stress=state_dict.get("stress", 0),
            fatigue=state_dict.get("fatigue", 0),
            focus=state_dict.get("focus", 0.5),
            engagement=state_dict.get("engagement", 0.5),
            cognitive_load=state_dict.get("cognitive_load", 0.5),
            ux_mode=state_dict.get("ux_mode", "normal"),
            confidence=state_dict.get("inference_confidence", 0.5),
            trend=state_dict.get("trend", "stable"),
            stage_payload_snapshot=dict(state_dict),
        )
        await _safe_emit(self._bus, "state.estimated", event)
