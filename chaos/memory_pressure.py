"""Memory pressure — grows event queues to test backpressure."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from simulation.simulation_models import ChaosEvent
from utils.logger import get_logger

if TYPE_CHECKING:
    from events.event_store import EventStore
    from streaming.ingestion import SensorIngestionPipeline

logger = get_logger(__name__)


class MemoryPressure:
    """Grows event queue rapidly to test backpressure activation."""

    def __init__(
        self, event_store: "EventStore", ingestion_pipeline: "SensorIngestionPipeline"
    ) -> None:
        self.event_store = event_store
        self.pipeline = ingestion_pipeline

    async def execute(self, duration_seconds: float) -> list[ChaosEvent]:
        """Apply memory pressure.

        Validates: backpressure activates, queue stays bounded.
        """
        from events.event_models import EventType, SystemEvent

        events: list[ChaosEvent] = []
        start = time.time()
        injected = 0

        while time.time() - start < duration_seconds:
            # Rapidly append events
            self.event_store.append(SystemEvent(
                event_type=EventType.SENSOR_RECEIVED,
                session_id="chaos_memory",
                payload={"pressure_test": True, "seq": injected},
            ))
            injected += 1

        events.append(ChaosEvent(
            event_type="memory_pressure",
            triggered_at=start,
            payload={"events_injected": injected},
            expected_recovery_within_seconds=10.0,
        ))

        logger.info("memory_pressure_complete", injected=injected)
        return events
