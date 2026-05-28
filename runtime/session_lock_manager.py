"""Per-session asyncio.Lock registry for concurrency safety."""

import asyncio


class SessionLockManager:
    """Per-session asyncio.Lock registry.

    Ensures no two concurrent coroutines mutate the same session state.
    """

    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}

    def get_lock(self, session_id: str) -> asyncio.Lock:
        """Get or create a lock for a session."""
        if session_id not in self._locks:
            self._locks[session_id] = asyncio.Lock()
        return self._locks[session_id]

    async def acquire(self, session_id: str) -> None:
        """Acquire the lock for a session."""
        lock = self.get_lock(session_id)
        await lock.acquire()

    async def release(self, session_id: str) -> None:
        """Release the lock for a session."""
        lock = self._locks.get(session_id)
        if lock and lock.locked():
            lock.release()

    def is_locked(self, session_id: str) -> bool:
        """Check if a session's lock is currently held."""
        lock = self._locks.get(session_id)
        return lock.locked() if lock else False
