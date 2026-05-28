"""Workload simulator — generates cognitive pressure events."""

from __future__ import annotations

import asyncio
import random
import time
from typing import AsyncIterator

from utils.logger import get_logger

logger = get_logger(__name__)


class WorkloadSimulator:
    """Generates cognitive pressure events for testing."""

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)
        self._stop_event = asyncio.Event()

    async def simulate_multitask_load(
        self, session_id: str, duration_seconds: float
    ) -> AsyncIterator[dict]:
        """Simulate multitasking cognitive load."""
        start = time.time()
        try:
            while not self._stop_event.is_set():
                if time.time() - start >= duration_seconds:
                    break
                yield {
                    "type": "multitask_load",
                    "session_id": session_id,
                    "timestamp": time.time(),
                    "active_tasks": self._rng.randint(3, 8),
                    "cognitive_load": self._rng.uniform(0.6, 0.95),
                }
                await asyncio.sleep(2.0)
        except asyncio.CancelledError:
            logger.info("multitask_sim_cancelled")
            raise

    async def simulate_cognitive_pressure(
        self, intensity: float, duration_seconds: float
    ) -> AsyncIterator[dict]:
        """Simulate sustained cognitive pressure."""
        start = time.time()
        try:
            while not self._stop_event.is_set():
                if time.time() - start >= duration_seconds:
                    break
                yield {
                    "type": "cognitive_pressure",
                    "timestamp": time.time(),
                    "intensity": intensity + self._rng.gauss(0, 0.05),
                    "duration_elapsed": time.time() - start,
                }
                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            logger.info("cognitive_pressure_cancelled")
            raise

    async def simulate_context_switching(
        self, switches_per_minute: int, duration_seconds: float
    ) -> AsyncIterator[dict]:
        """Simulate rapid context switching."""
        interval = 60.0 / max(switches_per_minute, 1)
        start = time.time()
        try:
            while not self._stop_event.is_set():
                if time.time() - start >= duration_seconds:
                    break
                yield {
                    "type": "context_switch",
                    "timestamp": time.time(),
                    "switches_per_minute": switches_per_minute,
                    "cognitive_load": min(1.0, switches_per_minute / 30.0),
                }
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            logger.info("context_switching_cancelled")
            raise

    def stop(self) -> None:
        self._stop_event.set()
