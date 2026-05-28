"""Behavioral context — tracks session behavioral patterns."""

from datetime import datetime, timezone


class BehavioralContext:
    """Tracks session behavioral patterns.

    Feeds into human_state/signals/behavior.py.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, dict] = {}

    def record_message(self, session_id: str) -> None:
        """Record that a message was sent in a session."""
        if session_id not in self._sessions:
            self._sessions[session_id] = {
                "message_count": 0,
                "last_message_time": None,
                "session_start": datetime.now(timezone.utc),
            }
        ctx = self._sessions[session_id]
        ctx["message_count"] += 1
        ctx["last_message_time"] = datetime.now(timezone.utc)

    def get_context(self, session_id: str) -> dict:
        """Get behavioral context for a session."""
        ctx = self._sessions.get(session_id, {})
        if not ctx:
            return {"message_count": 0}

        last = ctx.get("last_message_time")
        start = ctx.get("session_start", datetime.now(timezone.utc))
        now = datetime.now(timezone.utc)

        return {
            "message_count": ctx.get("message_count", 0),
            "session_duration_s": (now - start).total_seconds(),
            "time_since_last_s": (
                (now - last).total_seconds() if last else None
            ),
        }
