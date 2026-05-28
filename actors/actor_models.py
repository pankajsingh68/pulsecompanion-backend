"""Actor data models."""

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class ActorMessage(BaseModel):
    """Message sent to a session actor."""

    message_type: str
    session_id: str
    payload: dict = {}
    reply_to: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ActorStatus(BaseModel):
    """Status of a session actor."""

    session_id: str
    is_alive: bool = True
    queue_depth: int = 0
    last_processed: datetime | None = None
    total_processed: int = 0
