"""Append-only in-memory event log per session."""

from __future__ import annotations

from events.event_models import EventType, SystemEvent
from utils.logger import get_logger

logger = get_logger(__name__)


class EventStore:
    """Append-only in-memory event log per session.

    Designed for: debugging, demo playback, future ML training data.
    Future upgrade: swap list for SQLite or Redis Streams.
    """

    def __init__(self, max_events_per_session: int = 200) -> None:
        self._events: dict[str, list[SystemEvent]] = {}
        self.max_events = max_events_per_session

    def append(self, event: SystemEvent) -> None:
        """Append an event to the session's log."""
        sid = event.session_id
        if sid not in self._events:
            self._events[sid] = []
        self._events[sid].append(event)
        if len(self._events[sid]) > self.max_events:
            self._events[sid].pop(0)
        logger.debug("event_stored", type=event.event_type.value, session_id=sid)

    def get_session_events(
        self, session_id: str, event_type: EventType | None = None
    ) -> list[SystemEvent]:
        """Get all events for a session, optionally filtered by type."""
        events = self._events.get(session_id, [])
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        return events

    def get_recent(self, session_id: str, n: int = 10) -> list[SystemEvent]:
        """Get the N most recent events for a session."""
        return self._events.get(session_id, [])[-n:]

    def get_transition_history(self, session_id: str) -> list[SystemEvent]:
        """Get all mode transition events for a session."""
        return self.get_session_events(session_id, EventType.MODE_TRANSITION)
