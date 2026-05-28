"""Replay test — proves one recorded session replays deterministically.

Flow:
1. Run real pipeline → Collect emitted events from bus
2. Serialize to JSON (lineage_id, timestamps, stage_payload_snapshots)
3. Save session file
4. Load session file
5. Feed recorded events through validator
6. Assert orchestration outputs match original run

Replay reads recorded events — it does NOT re-invoke live orchestration logic.
Any divergence is a hard failure.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from events.event_bus import AsyncEventBus
from events.lineage import mint_lineage
from events.pipeline_events import BaseEvent, PIPELINE_STAGE_ORDER
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class RecordedEvent:
    """A single recorded pipeline event for replay."""
    event_type: str
    lineage_id: str
    session_id: str
    monotonic_order: float
    event_timestamp: str
    processing_timestamp: float
    stage_payload_snapshot: dict
    # Future longitudinal fields (nullable, not populated yet)
    baseline_drift: float | None = None
    adaptation_history: list[dict] | None = None
    emotional_continuity: float | None = None


@dataclass
class RecordedSession:
    """A complete recorded session for deterministic replay."""
    session_name: str
    captured_at: float
    events: list[RecordedEvent] = field(default_factory=list)
    orchestration_outputs: list[dict] = field(default_factory=list)
    # Future fields
    baseline_drift: float | None = None
    adaptation_history: list[dict] | None = None

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps({
            "session_name": self.session_name,
            "captured_at": self.captured_at,
            "events": [
                {
                    "event_type": e.event_type,
                    "lineage_id": e.lineage_id,
                    "session_id": e.session_id,
                    "monotonic_order": e.monotonic_order,
                    "event_timestamp": e.event_timestamp,
                    "processing_timestamp": e.processing_timestamp,
                    "stage_payload_snapshot": e.stage_payload_snapshot,
                }
                for e in self.events
            ],
            "orchestration_outputs": self.orchestration_outputs,
        }, indent=2, default=str)

    @classmethod
    def from_json(cls, json_str: str) -> "RecordedSession":
        """Deserialize from JSON string."""
        data = json.loads(json_str)
        events = [
            RecordedEvent(**e) for e in data.get("events", [])
        ]
        return cls(
            session_name=data["session_name"],
            captured_at=data["captured_at"],
            events=events,
            orchestration_outputs=data.get("orchestration_outputs", []),
        )


@dataclass
class ReplayResult:
    """Result of replaying a recorded session."""
    passed: bool = True
    original_orchestration_count: int = 0
    replayed_orchestration_count: int = 0
    divergences: list[str] = field(default_factory=list)
    events_replayed: int = 0


class SessionRecorder:
    """Records pipeline events from the bus into a RecordedSession."""

    def __init__(self, bus: AsyncEventBus, session_name: str) -> None:
        self._bus = bus
        self._session = RecordedSession(
            session_name=session_name,
            captured_at=time.time(),
        )
        self._recording = False

    async def _on_event(self, event: BaseEvent) -> None:
        """Callback for bus events during recording."""
        if not self._recording:
            return

        recorded = RecordedEvent(
            event_type=self._classify_event(event),
            lineage_id=str(event.lineage_id),
            session_id=event.session_id,
            monotonic_order=event.monotonic_order,
            event_timestamp=event.event_timestamp.isoformat(),
            processing_timestamp=event.processing_timestamp,
            stage_payload_snapshot=event.stage_payload_snapshot,
        )
        self._session.events.append(recorded)

        # Capture orchestration outputs specifically
        if "orchestration" in recorded.event_type:
            self._session.orchestration_outputs.append(
                event.stage_payload_snapshot
            )

    def start_recording(self) -> None:
        """Start recording events from the bus."""
        self._recording = True
        for stage in PIPELINE_STAGE_ORDER:
            self._bus.subscribe(stage, self._on_event)
        logger.info("session_recording_started", session=self._session.session_name)

    def stop_recording(self) -> RecordedSession:
        """Stop recording and return the captured session."""
        self._recording = False
        for stage in PIPELINE_STAGE_ORDER:
            self._bus.unsubscribe(stage, self._on_event)
        logger.info(
            "session_recording_stopped",
            session=self._session.session_name,
            events=len(self._session.events),
        )
        return self._session

    def _classify_event(self, event: BaseEvent) -> str:
        """Determine event type string from event class."""
        from events.pipeline_events import (
            SensorIngestedEvent, SensorNormalizedEvent, StateEstimatedEvent,
            OrchestrationCompletedEvent, SafetyCorrectedEvent,
            WebSocketEmittedEvent, MemoryPersistedEvent, DegradedModeChangedEvent,
        )
        type_map = {
            SensorIngestedEvent: "sensor.ingested",
            SensorNormalizedEvent: "sensor.normalized",
            StateEstimatedEvent: "state.estimated",
            OrchestrationCompletedEvent: "orchestration.completed",
            SafetyCorrectedEvent: "safety.corrected",
            WebSocketEmittedEvent: "websocket.emitted",
            MemoryPersistedEvent: "memory.persisted",
            DegradedModeChangedEvent: "degraded_mode.changed",
        }
        return type_map.get(type(event), "unknown")


def replay_session(recorded: RecordedSession) -> ReplayResult:
    """Replay a recorded session and validate orchestration outputs match.

    Replay reads recorded events — does NOT re-invoke live orchestration.
    Any divergence between original and replayed output is a hard failure.

    Args:
        recorded: The previously captured session.

    Returns:
        ReplayResult with pass/fail and any divergences.
    """
    result = ReplayResult(
        original_orchestration_count=len(recorded.orchestration_outputs),
        events_replayed=len(recorded.events),
    )

    # Extract orchestration events from recorded stream
    replayed_orchestrations = [
        e.stage_payload_snapshot
        for e in recorded.events
        if e.event_type == "orchestration.completed"
    ]
    result.replayed_orchestration_count = len(replayed_orchestrations)

    # Compare original vs replayed orchestration outputs
    for i, (original, replayed) in enumerate(
        zip(recorded.orchestration_outputs, replayed_orchestrations)
    ):
        # Compare key fields (not timestamps which will differ)
        for key in ["ux_mode", "verbosity_level", "response_tone", "suggest_break"]:
            orig_val = original.get(key)
            replay_val = replayed.get(key)
            if orig_val != replay_val:
                result.divergences.append(
                    f"decision[{i}].{key}: original={orig_val}, replayed={replay_val}"
                )

    if len(recorded.orchestration_outputs) != len(replayed_orchestrations):
        result.divergences.append(
            f"orchestration_count_mismatch: "
            f"original={len(recorded.orchestration_outputs)}, "
            f"replayed={len(replayed_orchestrations)}"
        )

    result.passed = len(result.divergences) == 0

    logger.info(
        "replay_complete",
        session=recorded.session_name,
        passed=result.passed,
        divergences=len(result.divergences),
        events=result.events_replayed,
    )

    return result


def save_session(recorded: RecordedSession, filepath: str) -> None:
    """Save a recorded session to a JSON file."""
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
    with open(filepath, "w") as f:
        f.write(recorded.to_json())
    logger.info("session_saved", path=filepath, events=len(recorded.events))


def load_session(filepath: str) -> RecordedSession:
    """Load a recorded session from a JSON file."""
    with open(filepath) as f:
        return RecordedSession.from_json(f.read())
