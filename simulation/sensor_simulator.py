"""Sensor simulator — generates realistic biometric streams."""

from __future__ import annotations

import asyncio
import math
import random
import time
from typing import AsyncIterator

from simulation.simulation_models import SensorSnapshot
from utils.logger import get_logger

logger = get_logger(__name__)


class SensorSimulator:
    """Generates realistic biometric sensor streams for testing.

    Uses sin oscillation + gaussian noise for physiologically plausible signals.
    Supports stress spikes, recovery curves, fatigue drift, and sensor dropouts.
    """

    def __init__(self, seed: int | None = None, sampling_interval_ms: int = 100) -> None:
        self._seed = seed
        self._rng = random.Random(seed)
        self._interval_ms = sampling_interval_ms
        self._tick = 0
        self._stop_event = asyncio.Event()
        self._tasks: list[asyncio.Task] = []

        # Baselines
        self._base_hr = 65.0 + self._rng.uniform(-5, 10)
        self._base_hrv = 55.0 + self._rng.uniform(-10, 10)
        self._base_gsr = 2.0 + self._rng.uniform(-0.5, 0.5)
        self._base_spo2 = 97.5 + self._rng.uniform(-0.5, 0.5)

        # Modifiers (applied by stress/recovery/fatigue methods)
        self._hr_modifier = 0.0
        self._hrv_modifier = 0.0
        self._gsr_modifier = 0.0
        self._dropout_sensors: dict[str, float] = {}  # sensor → end_time

    async def stream(
        self, session_id: str, duration_seconds: float
    ) -> AsyncIterator[SensorSnapshot]:
        """Generate a stream of sensor snapshots.

        Args:
            session_id: Session to generate for.
            duration_seconds: How long to stream.

        Yields:
            SensorSnapshot at each sampling interval.
        """
        start = time.time()
        interval_s = self._interval_ms / 1000.0

        try:
            while not self._stop_event.is_set():
                elapsed = time.time() - start
                if elapsed >= duration_seconds:
                    break

                self._tick += 1
                snapshot = self._generate_snapshot(session_id, elapsed)
                yield snapshot
                await asyncio.sleep(interval_s)
        except asyncio.CancelledError:
            logger.info("sensor_simulator_cancelled", session_id=session_id)
            raise

        logger.info("sensor_stream_complete", session_id=session_id, ticks=self._tick)

    def apply_stress_spike(self, intensity: float, duration_seconds: float) -> None:
        """Apply a stress spike — raises HR 20-40%, drops HRV 30-50%, raises GSR."""
        self._hr_modifier = self._base_hr * (0.2 + 0.2 * intensity)
        self._hrv_modifier = -self._base_hrv * (0.3 + 0.2 * intensity)
        self._gsr_modifier = 3.0 * intensity

    def apply_recovery_curve(self, duration_seconds: float) -> None:
        """Apply smooth exponential recovery to baseline."""
        # Decay modifiers toward zero
        self._hr_modifier *= 0.7
        self._hrv_modifier *= 0.7
        self._gsr_modifier *= 0.7

    def apply_fatigue_drift(self, rate: float) -> None:
        """Apply linear fatigue drift — HRV declines, HR elevates slowly."""
        self._hrv_modifier -= rate * 0.5
        self._hr_modifier += rate * 0.3

    def inject_dropout(
        self, sensor: str, duration_seconds: float
    ) -> None:
        """Inject a sensor dropout — returns None for that sensor during window."""
        self._dropout_sensors[sensor] = time.time() + duration_seconds

    def stop(self) -> None:
        """Signal the simulator to stop."""
        self._stop_event.set()

    def _generate_snapshot(self, session_id: str, elapsed: float) -> SensorSnapshot:
        """Generate a single snapshot with noise and modifiers."""
        now = time.time()

        # Check dropouts
        hr = self._compute_hr(elapsed) if not self._is_dropped("hr", now) else None
        hrv = self._compute_hrv(elapsed) if not self._is_dropped("hrv", now) else None
        gsr = self._compute_gsr(elapsed) if not self._is_dropped("gsr", now) else None
        spo2 = self._compute_spo2() if not self._is_dropped("spo2", now) else None

        quality = 1.0
        if hr is None or hrv is None:
            quality = 0.5 if (hr is not None or hrv is not None) else 0.0

        return SensorSnapshot(
            session_id=session_id,
            timestamp=now,
            hr=hr,
            hrv=hrv,
            gsr=gsr,
            spo2=spo2,
            source="simulated",
            quality=quality,
        )

    def _compute_hr(self, elapsed: float) -> float:
        """HR with sin oscillation + noise + modifiers."""
        oscillation = 3.0 * math.sin(elapsed * 0.1)
        noise = self._rng.gauss(0, 1.5)
        raw = self._base_hr + self._hr_modifier + oscillation + noise
        return round(max(40, min(200, raw)), 1)

    def _compute_hrv(self, elapsed: float) -> float:
        """HRV inversely correlated with stress, with noise."""
        oscillation = 4.0 * math.sin(elapsed * 0.07)
        noise = self._rng.gauss(0, 2.0)
        raw = self._base_hrv + self._hrv_modifier + oscillation + noise
        return round(max(5, min(150, raw)), 1)

    def _compute_gsr(self, elapsed: float) -> float:
        """GSR with slow drift + noise."""
        noise = self._rng.gauss(0, 0.2)
        raw = self._base_gsr + self._gsr_modifier + noise
        return round(max(0.1, min(20.0, raw)), 2)

    def _compute_spo2(self) -> float:
        """SpO2 — mostly stable with tiny noise."""
        noise = self._rng.gauss(0, 0.3)
        return round(max(90, min(100, self._base_spo2 + noise)), 1)

    def _is_dropped(self, sensor: str, now: float) -> bool:
        """Check if a sensor is in dropout window."""
        end_time = self._dropout_sensors.get(sensor)
        if end_time is None:
            return False
        if now >= end_time:
            del self._dropout_sensors[sensor]
            return False
        return True
