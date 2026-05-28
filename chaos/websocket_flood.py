"""WebSocket flood — sends synthetic events at high rate."""

from __future__ import annotations

import asyncio
import random
import time
from typing import TYPE_CHECKING

from simulation.simulation_models import ChaosEvent
from utils.logger import get_logger

if TYPE_CHECKING:
    from websocket.manager import ConnectionManager

logger = get_logger(__name__)


class WebSocketFlood:
    """Sends synthetic WebSocket events at target rate to test throttling."""

    def __init__(self, ws_manager: "ConnectionManager", seed: int | None = None) -> None:
        self.ws_manager = ws_manager
        self._rng = random.Random(seed)

    async def execute(
        self, rate_per_second: int, duration_seconds: float
    ) -> list[ChaosEvent]:
        """Flood WebSocket with events.

        Validates: throttler activates, queue stays bounded.
        """
        events: list[ChaosEvent] = []
        interval = 1.0 / max(rate_per_second, 1)
        start = time.time()
        sent = 0

        try:
            while time.time() - start < duration_seconds:
                sent += 1
                # Send to a test session
                await self.ws_manager.send_json("chaos_test", {
                    "type": "chaos_flood",
                    "sequence": sent,
                    "timestamp": time.time(),
                })
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            logger.info("websocket_flood_cancelled")
            raise

        events.append(ChaosEvent(
            event_type="websocket_flood",
            triggered_at=start,
            payload={"total_sent": sent, "rate": rate_per_second},
            expected_recovery_within_seconds=5.0,
        ))

        logger.info("websocket_flood_complete", sent=sent, duration=duration_seconds)
        return events
