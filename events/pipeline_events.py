"""Typed pipeline event contracts — one per pipeline stage.

Every event carries: lineage_id, session_id, event_timestamp,
processing_timestamp, stage_payload_snapshot.

These events are emitted by the production pipeline at each stage boundary.
Validators observe them — they never create them.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID


@dataclass
class BaseEvent:
    """Base contract for all pipeline events.

    Every event is self-sufficient for deterministic replay:
    - Full stage_payload_snapshot (not just metadata)
    - Monotonic ordering field alongside wall-clock timestamp
    """
    lineage_id: UUID
    session_id: str
    event_timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    processing_timestamp: float = field(default_factory=time.monotonic)
    stage_payload_snapshot: dict = field(default_factory=dict)
    monotonic_order: float = field(default_factory=time.monotonic)


@dataclass
class SensorIngestedEvent(BaseEvent):
    """Emitted when a raw biometric snapshot is accepted into the pipeline."""
    hr: float | None = None
    hrv: float | None = None
    gsr: float | None = None
    source: str = "manual"
    quality: float = 1.0


@dataclass
class SensorNormalizedEvent(BaseEvent):
    """Emitted when sensor normalization completes."""
    hr_normalized: float | None = None
    hrv_normalized: float | None = None
    reliability_report: dict = field(default_factory=dict)


@dataclass
class StateEstimatedEvent(BaseEvent):
    """Emitted when HumanStateEngine produces a RichHumanState."""
    stress: float = 0.0
    fatigue: float = 0.0
    focus: float = 0.5
    engagement: float = 0.5
    cognitive_load: float = 0.5
    ux_mode: str = "normal"
    confidence: float = 0.5
    trend: str = "stable"


@dataclass
class OrchestrationCompletedEvent(BaseEvent):
    """Emitted when UXOrchestrator produces a UXStrategy."""
    ux_mode: str = "normal"
    verbosity_level: str = "normal"
    response_tone: str = "neutral"
    suggest_break: bool = False
    suppress_notifications: bool = False
    orchestration_confidence: float = 0.5
    reasoning: list[str] = field(default_factory=list)


@dataclass
class SafetyCorrectedEvent(BaseEvent):
    """Emitted when the safety layer applies corrections."""
    was_limited: bool = False
    limited_fields: list[str] = field(default_factory=list)
    original_mode: str = "normal"
    corrected_mode: str = "normal"
    guard_reasoning: str = ""


@dataclass
class WebSocketEmittedEvent(BaseEvent):
    """Emitted when a payload is dispatched to the WebSocket layer."""
    event_type: str = ""
    payload_size_bytes: int = 0
    target_session: str = ""
    delivery_success: bool = True


@dataclass
class MemoryPersistedEvent(BaseEvent):
    """Emitted when a memory record is written to storage."""
    tier: str = "working"
    importance_score: float = 0.0
    episode_type: str | None = None
    collection_name: str = ""


@dataclass
class DegradedModeChangedEvent(BaseEvent):
    """Emitted when the system enters or exits degraded mode."""
    previous_mode: str = "normal"
    new_mode: str = "degraded"
    reason: str = ""
    affected_subsystems: list[str] = field(default_factory=list)


# Event type string constants — used for bus subscription
EVENT_TYPES = {
    "sensor.ingested": SensorIngestedEvent,
    "sensor.normalized": SensorNormalizedEvent,
    "state.estimated": StateEstimatedEvent,
    "orchestration.completed": OrchestrationCompletedEvent,
    "safety.corrected": SafetyCorrectedEvent,
    "websocket.emitted": WebSocketEmittedEvent,
    "memory.persisted": MemoryPersistedEvent,
    "degraded_mode.changed": DegradedModeChangedEvent,
}

# Ordered pipeline stage sequence for validation
PIPELINE_STAGE_ORDER = [
    "sensor.ingested",
    "sensor.normalized",
    "state.estimated",
    "orchestration.completed",
    "safety.corrected",
    "websocket.emitted",
    "memory.persisted",
]
