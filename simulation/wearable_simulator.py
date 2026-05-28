"""Wearable simulator — applies device-realistic degradation to sensor streams."""

from __future__ import annotations

import asyncio
import random
import time
from typing import AsyncIterator

from simulation.sensor_simulator import SensorSimulator
from simulation.simulation_models import SensorSnapshot
from utils.logger import get_logger

logger = get_logger(__name__)


class WearableSimulator:
    """Wraps SensorSimulator with wearable-realistic degradation.

    Simulates Samsung Galaxy Watch 4/5/6 characteristics:
    - HR: 1Hz sampling
    - HRV: computed per 5min window
    - GSR: 20Hz (downsampled here)
    - Packet jitter, loss, stale packets, disconnects
    """

    def __init__(self, device_id: str, seed: int | None = None) -> None:
        self.device_id = device_id
        self._rng = random.Random(seed)
        self._sensor_sim = SensorSimulator(seed=seed, sampling_interval_ms=1000)
        self._stop_event = asyncio.Event()

        # Degradation parameters
        self.jitter_ms: float = 50.0
        self.packet_loss_rate: float = 0.02
        self.stale_packet_probability: float = 0.01
        self.disconnect_events: list[tuple[float, float]] = []

        self._last_snapshot: SensorSnapshot | None = None
        self._tasks: list[asyncio.Task] = []

    async def stream(
        self, session_id: str, duration_seconds: float
    ) -> AsyncIterator[SensorSnapshot | None]:
        """Stream with wearable-realistic degradation applied.

        Yields SensorSnapshot or None (dropped packet).
        """
        start = time.time()

        try:
            async for snapshot in self._sensor_sim.stream(session_id, duration_seconds):
                elapsed = time.time() - start

                # Check disconnect windows
                if self._is_disconnected(elapsed):
                    yield None
                    continue

                # Packet loss
                if self._rng.random() < self.packet_loss_rate:
                    yield None
                    continue

                # Stale packet (repeat previous)
                if self._last_snapshot and self._rng.random() < self.stale_packet_probability:
                    yield self._last_snapshot
                    continue

                # Apply jitter to timestamp
                jitter_s = self._rng.gauss(0, self.jitter_ms / 1000.0)
                snapshot = snapshot.model_copy(update={
                    "timestamp": snapshot.timestamp + jitter_s,
                })

                self._last_snapshot = snapshot
                yield snapshot
        except asyncio.CancelledError:
            logger.info("wearable_simulator_cancelled", device_id=self.device_id)
            raise

    def add_disconnect(self, at_second: float, duration_seconds: float) -> None:
        """Schedule a disconnect event."""
        self.disconnect_events.append((at_second, duration_seconds))

    def _is_disconnected(self, elapsed: float) -> bool:
        """Check if currently in a disconnect window."""
        for start, duration in self.disconnect_events:
            if start <= elapsed < start + duration:
                return True
        return False

    def stop(self) -> None:
        self._stop_event.set()
        self._sensor_sim.stop()
