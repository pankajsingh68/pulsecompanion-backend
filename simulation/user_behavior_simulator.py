"""User behavior simulator — generates behavioral context events."""

from __future__ import annotations

import asyncio
import random
import time
from typing import AsyncIterator

from utils.logger import get_logger

logger = get_logger(__name__)


class UserBehaviorSimulator:
    """Generates BehavioralContext-compatible events for testing."""

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)
        self._stop_event = asyncio.Event()

    async def typing_burst(
        self, wpm: int, duration_seconds: float
    ) -> AsyncIterator[dict]:
        """Simulate a typing burst — high cognitive load signal."""
        start = time.time()
        chars_per_sec = (wpm * 5) / 60.0
        try:
            while not self._stop_event.is_set():
                elapsed = time.time() - start
                if elapsed >= duration_seconds:
                    break
                yield {
                    "type": "typing_burst",
                    "timestamp": time.time(),
                    "wpm": wpm,
                    "chars_typed": int(chars_per_sec * elapsed),
                    "cognitive_load_signal": min(1.0, wpm / 100.0),
                }
                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            logger.info("typing_burst_cancelled")
            raise

    async def message_flood(
        self, rate_per_minute: int, duration_seconds: float
    ) -> AsyncIterator[dict]:
        """Simulate rapid message sending — interruption simulation."""
        interval = 60.0 / rate_per_minute
        start = time.time()
        count = 0
        try:
            while not self._stop_event.is_set():
                if time.time() - start >= duration_seconds:
                    break
                count += 1
                yield {
                    "type": "message_sent",
                    "timestamp": time.time(),
                    "message_count": count,
                    "rate_per_minute": rate_per_minute,
                }
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            logger.info("message_flood_cancelled")
            raise

    async def idle_period(
        self, duration_seconds: float
    ) -> AsyncIterator[dict]:
        """Simulate idle period — recovery signal."""
        start = time.time()
        try:
            yield {
                "type": "idle_start",
                "timestamp": time.time(),
                "expected_duration": duration_seconds,
            }
            while not self._stop_event.is_set():
                if time.time() - start >= duration_seconds:
                    break
                await asyncio.sleep(5.0)
            yield {
                "type": "idle_end",
                "timestamp": time.time(),
                "actual_duration": time.time() - start,
            }
        except asyncio.CancelledError:
            logger.info("idle_period_cancelled")
            raise

    async def context_switch_storm(
        self, switches_per_minute: int, duration_seconds: float
    ) -> AsyncIterator[dict]:
        """Simulate rapid context switching — multitasking overload."""
        interval = 60.0 / switches_per_minute
        start = time.time()
        count = 0
        contexts = ["email", "code", "chat", "docs", "browser", "terminal"]
        try:
            while not self._stop_event.is_set():
                if time.time() - start >= duration_seconds:
                    break
                count += 1
                yield {
                    "type": "context_switch",
                    "timestamp": time.time(),
                    "from_context": self._rng.choice(contexts),
                    "to_context": self._rng.choice(contexts),
                    "switch_count": count,
                    "cognitive_load_signal": min(1.0, switches_per_minute / 30.0),
                }
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            logger.info("context_switch_storm_cancelled")
            raise

    def stop(self) -> None:
        self._stop_event.set()
