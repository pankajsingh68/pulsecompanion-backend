"""Event-driven orchestration models."""

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class OrchestrationTrigger(str, Enum):
    CHAT_MESSAGE = "chat_message"
    SENSOR_UPDATE = "sensor_update"
    TIMER_TICK = "timer_tick"
    MANUAL = "manual"


class OrchestrationRequest(BaseModel):
    """Request to recompute orchestration for a session."""

    session_id: str
    trigger: OrchestrationTrigger
    human_state: dict
    reliability_report: dict = {}
    triggered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict = {}
