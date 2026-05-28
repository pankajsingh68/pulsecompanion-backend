"""Stream event models."""

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class StreamEvent(BaseModel):
    """A streaming event emitted by the ingestion pipeline."""

    event_type: str
    session_id: str
    payload: dict = {}
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = "system"
