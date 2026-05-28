"""WebSocket throttle — rate-limits outgoing messages per session."""

from datetime import datetime, timezone


class WebSocketThrottle:
    """Rate-limits outgoing WebSocket messages per session.

    Max: 10 messages/second per session (configurable).
    Prevents: flooding frontend with rapid sensor updates.
    """

    def __init__(self, max_per_second: float = 10.0) -> None:
        self.max_per_second = max_per_second
        self._window_start: dict[str, datetime] = {}
        self._count: dict[str, int] = {}

    def should_send(self, session_id: str) -> bool:
        """Check if we can send another message to this session."""
        now = datetime.now(timezone.utc)
        start = self._window_start.get(session_id)

        if start is None or (now - start).total_seconds() >= 1.0:
            # New window
            self._window_start[session_id] = now
            self._count[session_id] = 0
            return True

        count = self._count.get(session_id, 0)
        return count < self.max_per_second

    def mark_sent(self, session_id: str) -> None:
        """Record that a message was sent."""
        self._count[session_id] = self._count.get(session_id, 0) + 1
