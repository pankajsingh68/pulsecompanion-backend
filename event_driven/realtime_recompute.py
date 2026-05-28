"""Debounced recompute trigger for realtime sensor streams."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from utils.logger import get_logger

if TYPE_CHECKING:
    from event_driven.event_models import OrchestrationRequest
    from event_driven.strategy_dispatcher import StrategyDispatcher

logger = get_logger(__name__)


class RealtimeRecompute:
    """Debounced recompute trigger.

    Prevents orchestration thrashing when sensor events arrive faster
    than the system can process them.
    Minimum recompute interval: 3 seconds per session.
    """

    def __init__(
        self,
        dispatcher: "StrategyDispatcher",
        min_interval_seconds: float = 3.0,
    ) -> None:
        self.dispatcher = dispatcher
        self.min_interval = min_interval_seconds
        self._last_recompute: dict[str, datetime] = {}
        self._pending: dict[str, "OrchestrationRequest"] = {}

    async def trigger(self, request: "OrchestrationRequest") -> None:
        """Trigger a recompute, respecting debounce interval.

        If within cooldown: queues the request for later.
        If cooldown expired: dispatches immediately.
        """
        session_id = request.session_id
        now = datetime.now(timezone.utc)

        last = self._last_recompute.get(session_id)
        if last and (now - last).total_seconds() < self.min_interval:
            # Within cooldown — store as pending
            self._pending[session_id] = request
            logger.debug(
                "recompute_debounced",
                session_id=session_id,
            )
            return

        # Dispatch immediately
        self._last_recompute[session_id] = now
        self._pending.pop(session_id, None)
        await self.dispatcher.dispatch(request)
