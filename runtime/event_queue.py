"""Per-session asyncio.Queue for serialized event processing."""

import asyncio


class SessionEventQueue:
    """Per-session asyncio.Queue for serialized event processing.

    Prevents race conditions when multiple sensor events
    arrive for the same session simultaneously.
    Max queue size: 50 events per session (drop oldest on overflow).
    """

    MAX_QUEUE_SIZE = 50

    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue] = {}

    def get_queue(self, session_id: str) -> asyncio.Queue:
        """Get or create a queue for a session."""
        if session_id not in self._queues:
            self._queues[session_id] = asyncio.Queue(maxsize=self.MAX_QUEUE_SIZE)
        return self._queues[session_id]

    async def enqueue(self, session_id: str, event: dict) -> None:
        """Add event to session queue. Drops oldest if full."""
        queue = self.get_queue(session_id)
        if queue.full():
            try:
                queue.get_nowait()  # drop oldest
            except asyncio.QueueEmpty:
                pass
        await queue.put(event)

    async def dequeue(self, session_id: str) -> dict:
        """Get next event from session queue (blocks if empty)."""
        queue = self.get_queue(session_id)
        return await queue.get()

    def queue_depth(self, session_id: str) -> int:
        """Get current queue depth for a session."""
        queue = self._queues.get(session_id)
        return queue.qsize() if queue else 0
