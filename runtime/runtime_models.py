"""Runtime data models."""

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class SessionState(BaseModel):
    """Tracks runtime state of a session."""

    session_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_locked: bool = False
    pending_events: int = 0
