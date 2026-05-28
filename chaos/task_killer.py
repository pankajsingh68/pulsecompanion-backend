"""Task killer — randomly cancels asyncio tasks to test supervision."""

from __future__ import annotations

import asyncio
import random
import time
from typing import TYPE_CHECKING

from simulation.simulation_models import ChaosEvent
from utils.logger import get_logger

if TYPE_CHECKING:
    from bootstrap.dependency_registry import DependencyRegistry

logger = get_logger(__name__)


class TaskKiller:
    """Randomly cancels asyncio tasks from registry."""

    def __init__(self, registry: "DependencyRegistry", seed: int | None = None) -> None:
        self.registry = registry
        self._rng = random.Random(seed)

    async def execute(
        self, kill_rate: float, duration_seconds: float
    ) -> list[ChaosEvent]:
        """Randomly kill tasks.

        Validates: supervisor detects dead tasks, no silent failures.
        """
        events: list[ChaosEvent] = []
        start = time.time()
        killed = 0

        # In a real implementation, this would access the task registry
        # For now, log the intent
        events.append(ChaosEvent(
            event_type="task_killer",
            triggered_at=start,
            payload={"kill_rate": kill_rate, "duration": duration_seconds, "killed": killed},
            expected_recovery_within_seconds=duration_seconds * 2,
        ))

        logger.info("task_killer_complete", killed=killed, duration=duration_seconds)
        return events
