"""Stream corruption — injects invalid sensor data."""

from __future__ import annotations

import random
import time
from typing import TYPE_CHECKING

from simulation.simulation_models import ChaosEvent
from utils.logger import get_logger

if TYPE_CHECKING:
    from streaming.ingestion import SensorIngestionPipeline

logger = get_logger(__name__)


class StreamCorruption:
    """Injects corrupted sensor data to test pipeline resilience."""

    def __init__(
        self, ingestion_pipeline: "SensorIngestionPipeline", seed: int | None = None
    ) -> None:
        self.pipeline = ingestion_pipeline
        self._rng = random.Random(seed)

    async def execute(self, duration_seconds: float) -> list[ChaosEvent]:
        """Inject corrupted packets.

        Injects: NaN values, negative timestamps, out-of-range values.
        Validates: pipeline rejects without crashing.
        """
        from sensors.models import BiometricSnapshot, SensorSource

        events: list[ChaosEvent] = []
        start = time.time()
        injected = 0
        rejected = 0

        corruptions = [
            {"hr": float("nan"), "hrv": 45},
            {"hr": -10, "hrv": 45},
            {"hr": 500, "hrv": 45},
            {"hr": 72, "hrv": -5},
            {"hr": 72, "hrv": 999},
        ]

        while time.time() - start < duration_seconds:
            corruption = self._rng.choice(corruptions)
            snapshot = BiometricSnapshot(
                session_id="chaos_corruption",
                hr=corruption.get("hr"),
                hrv=corruption.get("hrv"),
                source=SensorSource.MOCK,
            )
            try:
                await self.pipeline.ingest("chaos_corruption", snapshot)
                injected += 1
            except Exception:
                rejected += 1

        events.append(ChaosEvent(
            event_type="stream_corruption",
            triggered_at=start,
            payload={"injected": injected, "rejected": rejected},
            expected_recovery_within_seconds=5.0,
        ))

        logger.info("stream_corruption_complete", injected=injected, rejected=rejected)
        return events
