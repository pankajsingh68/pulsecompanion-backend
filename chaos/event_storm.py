"""Event storm — floods recompute engine with rapid state changes."""

from __future__ import annotations

import random
import time
from typing import TYPE_CHECKING

from simulation.simulation_models import ChaosEvent
from utils.logger import get_logger

if TYPE_CHECKING:
    from events.event_store import EventStore
    from streaming.recompute_engine import RecomputeEngine

logger = get_logger(__name__)


class EventStorm:
    """Floods recompute engine with rapid state-change events."""

    def __init__(
        self,
        recompute_engine: "RecomputeEngine",
        event_store: "EventStore",
        seed: int | None = None,
    ) -> None:
        self.recompute_engine = recompute_engine
        self.event_store = event_store
        self._rng = random.Random(seed)

    async def execute(self, duration_seconds: float) -> list[ChaosEvent]:
        """Flood recompute engine with rapid events.

        Validates: AdaptiveRecomputeScheduler throttles correctly.
        """
        events: list[ChaosEvent] = []
        start = time.time()
        count = 0

        while time.time() - start < duration_seconds:
            count += 1
            hint = {"hr": 60 + self._rng.randint(0, 50), "hrv": 20 + self._rng.randint(0, 40)}
            await self.recompute_engine.recompute("chaos_storm", hint)

        events.append(ChaosEvent(
            event_type="event_storm",
            triggered_at=start,
            payload={"total_recomputes": count},
            expected_recovery_within_seconds=10.0,
        ))

        logger.info("event_storm_complete", recomputes=count)
        return events
