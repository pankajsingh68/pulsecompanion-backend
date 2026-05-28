"""Event type definitions for the PulseCompanion event system."""

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class EventType(str, Enum):
    STATE_COMPUTED = "state_computed"
    UX_STRATEGY_UPDATED = "ux_strategy_updated"
    MODE_TRANSITION = "mode_transition"
    SENSOR_RECEIVED = "sensor_received"
    BASELINE_UPDATED = "baseline_updated"
    RELIABILITY_WARNING = "reliability_warning"
    BREAK_SUGGESTED = "break_suggested"
    FATIGUE_RISING = "fatigue_rising"
    RECOVERY_DETECTED = "recovery_detected"
    COGNITIVE_OVERLOAD = "cognitive_overload"
    SESSION_STARTED = "session_started"
    SESSION_ENDED = "session_ended"


class SystemEvent(BaseModel):
    """A system event for logging, debugging, and future ML training."""

    event_type: EventType
    session_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    payload: dict = {}
    severity: str = "info"
    source: str = "system"
