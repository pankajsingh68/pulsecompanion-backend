"""Isolated runtime container per session."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from runtime.runtime_models import SessionState
from runtime.session_lock_manager import SessionLockManager
from runtime.event_queue import SessionEventQueue


class SessionRuntime:
    """Isolated runtime container per session.

    Owns: lock, event queue, local state cache.
    All orchestration mutations go through this.
    Each session behaves like an isolated adaptive system.
    """

    def __init__(
        self,
        lock_manager: SessionLockManager,
        event_queue: SessionEventQueue,
    ) -> None:
        self.lock_manager = lock_manager
        self.event_queue = event_queue
        self._session_states: dict[str, SessionState] = {}

    async def safe_update(
        self, session_id: str, update_fn: Callable
    ) -> Any:
        """Acquire session lock, run update_fn, release lock.

        All orchestrator writes must use this method.
        """
        async with self.lock_manager.get_lock(session_id):
            self._touch(session_id)
            return await update_fn()

    def get_session_state(self, session_id: str) -> SessionState:
        """Get or create session state."""
        if session_id not in self._session_states:
            self._session_states[session_id] = SessionState(session_id=session_id)
        return self._session_states[session_id]

    def _touch(self, session_id: str) -> None:
        """Update last_updated timestamp."""
        state = self.get_session_state(session_id)
        state.last_updated = datetime.now(timezone.utc)
