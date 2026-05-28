"""Latency injector — simulates network instability."""

from __future__ import annotations

import asyncio
import random
from typing import Callable

from utils.logger import get_logger

logger = get_logger(__name__)


class LatencyInjector:
    """Applies random delays to simulate network instability."""

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    async def inject(
        self, target_fn: Callable, delay_ms_range: tuple[int, int]
    ):
        """Call target_fn with injected latency.

        Args:
            target_fn: Async callable to wrap.
            delay_ms_range: (min_ms, max_ms) delay range.
        """
        delay_ms = self._rng.randint(delay_ms_range[0], delay_ms_range[1])
        await asyncio.sleep(delay_ms / 1000.0)
        return await target_fn()
