"""Event batcher — batches rapid sensor events within a time window."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone


class EventBatcher:
    """Batches rapid sensor events within a time window.

    If 5 events arrive in 1 second: batch → single recompute.
    Reduces orchestration thrashing during fast wearable streams.
    Window: 1.0 seconds. Max batch size: 10.
    """

    def __init__(
        self, window_seconds: float = 1.0, max_batch_size: int = 10
    ) -> None:
        self.window = window_seconds
        self.max_batch_size = max_batch_size
        self._batches: dict[str, list[dict]] = {}
        self._batch_start: dict[str, datetime] = {}

    async def add(self, session_id: str, event: dict) -> None:
        """Add an event to the current batch for a session."""
        now = datetime.now(timezone.utc)

        if session_id not in self._batches:
            self._batches[session_id] = []
            self._batch_start[session_id] = now

        self._batches[session_id].append(event)

        # Cap batch size
        if len(self._batches[session_id]) > self.max_batch_size:
            self._batches[session_id].pop(0)

    async def flush(self, session_id: str) -> list[dict]:
        """Flush and return the current batch for a session."""
        batch = self._batches.pop(session_id, [])
        self._batch_start.pop(session_id, None)
        return batch

    def is_window_expired(self, session_id: str) -> bool:
        """Check if the batch window has expired."""
        start = self._batch_start.get(session_id)
        if start is None:
            return True
        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        return elapsed >= self.window
