"""Lightweight session actor — processes messages serially."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from actors.actor_models import ActorMessage, ActorStatus
from utils.logger import get_logger

if TYPE_CHECKING:
    from event_driven.strategy_dispatcher import StrategyDispatcher

logger = get_logger(__name__)


class SessionActor:
    """Lightweight actor per session.

    Processes messages from its asyncio.Queue serially.
    Owns: local state cache, strategy history reference, event queue.

    Phase 5 upgrade path:
    - Replace asyncio.Queue with Ray actor or asyncio TaskGroup
    - Enable horizontal scaling across processes
    """

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=50)
        self._total_processed: int = 0
        self._last_processed: datetime | None = None
        self._is_alive: bool = True

    async def send(self, message: ActorMessage) -> None:
        """Send a message to this actor's queue."""
        if self._queue.full():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        await self._queue.put(message)

    def get_status(self) -> ActorStatus:
        """Get current actor status."""
        return ActorStatus(
            session_id=self.session_id,
            is_alive=self._is_alive,
            queue_depth=self._queue.qsize(),
            last_processed=self._last_processed,
            total_processed=self._total_processed,
        )
