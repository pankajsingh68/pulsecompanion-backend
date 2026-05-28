"""Orchestrator debouncer — prevents recompute thrashing."""

from datetime import datetime, timezone


class OrchestratorDebouncer:
    """Prevents recompute if last recompute < min_interval ago.

    Per-session. Does NOT drop events — queues them.
    """

    def __init__(self, min_interval_seconds: float = 3.0) -> None:
        self.min_interval = min_interval_seconds
        self._last_recompute: dict[str, datetime] = {}

    def should_recompute(self, session_id: str) -> bool:
        """Check if enough time has passed since last recompute."""
        last = self._last_recompute.get(session_id)
        if last is None:
            return True
        elapsed = (datetime.now(timezone.utc) - last).total_seconds()
        return elapsed >= self.min_interval

    def mark_recomputed(self, session_id: str) -> None:
        """Mark that a recompute just happened."""
        self._last_recompute[session_id] = datetime.now(timezone.utc)
