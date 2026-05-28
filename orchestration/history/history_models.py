"""Models for strategy history tracking."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from orchestration.models import UXStrategy


class StrategyTransition(BaseModel):
    """Records a meaningful UX strategy transition."""

    session_id: str
    from_mode: str | None
    to_mode: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reasoning: list[str] = []
    confidence: float = 0.5
    triggered_by: str = "chat_message"


class StrategySnapshot(BaseModel):
    """A point-in-time snapshot of strategy + transition + state."""

    strategy: dict  # UXStrategy as dict
    transition: StrategyTransition
    state_at_time: dict = {}
