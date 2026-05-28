"""Clock drift — injects timestamp offsets to test temporal alignment."""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from simulation.simulation_models import ChaosEvent
from utils.logger import get_logger

if TYPE_CHECKING:
    from streaming.sync_engine import SyncEngine

logger = get_logger(__name__)


class ClockDrift:
    """Injects increasing timestamp offsets into the sync engine."""

    def __init__(self, sync_engine: "SyncEngine", seed: int | None = None) -> None:
        self.sync_engine = sync_engine

    async def execute(
        self, drift_ms_per_second: float, duration_seconds: float
    ) -> list[ChaosEvent]:
        """Inject clock drift.

        Validates: TimestampAligner detects drift, LateEventHandler handles correctly.
        """
        events: list[ChaosEvent] = []
        start = time.time()
        total_drift_ms = 0.0

        while time.time() - start < duration_seconds:
            total_drift_ms += drift_ms_per_second
            # Inject event with drifted timestamp
            self.sync_engine.ingest_event("chaos_drift", {
                "hr": 72,
                "timestamp": time.time() - (total_drift_ms / 1000.0),
                "drifted": True,
            })
            await asyncio.sleep(1.0)

        events.append(ChaosEvent(
            event_type="clock_drift",
            triggered_at=start,
            payload={"total_drift_ms": total_drift_ms, "rate": drift_ms_per_second},
            expected_recovery_within_seconds=5.0,
        ))

        logger.info("clock_drift_complete", total_drift_ms=round(total_drift_ms))
        return events
