"""Lightweight session actor placeholder.

Phase 5 upgrade: replace with true actor model (ray/asyncio actors).
Documents the future actor model contract.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from runtime.session_runtime import SessionRuntime


class SessionActorStub:
    """Stub that wraps SessionRuntime with actor-style message passing interface.

    Current: delegates directly to SessionRuntime.safe_update().
    Future: true actor with mailbox, supervision, and horizontal scaling.
    """

    def __init__(self, session_id: str, runtime: "SessionRuntime") -> None:
        self.session_id = session_id
        self.runtime = runtime

    async def send(self, message: dict) -> None:
        """Send a message to this session's actor."""
        await self.runtime.event_queue.enqueue(self.session_id, message)
