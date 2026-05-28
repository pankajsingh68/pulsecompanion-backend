"""Debug and inspection data models."""

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class ReplayFrame(BaseModel):
    """A single frame in a session replay."""

    frame_index: int
    timestamp: datetime
    event: dict | None = None
    state_snapshot: dict | None = None
    strategy_snapshot: dict | None = None
    transition: dict | None = None


class InspectionReport(BaseModel):
    """Summary inspection report for a session."""

    session_id: str
    total_events: int = 0
    total_strategy_changes: int = 0
    mode_distribution: dict[str, int] = {}
    avg_confidence: float = 0.0
    safety_guard_triggers: int = 0
    stress_trend: list[float] = []
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
