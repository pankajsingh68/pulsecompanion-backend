"""Degraded runtime — forces degraded mode to test fallback behavior."""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from simulation.simulation_models import ChaosEvent
from utils.logger import get_logger

if TYPE_CHECKING:
    from streaming.degradation import DegradedModeManager

logger = get_logger(__name__)


class DegradedRuntime:
    """Forces degraded mode by simulating sensor failure."""

    def __init__(self, degraded_mode_manager: "DegradedModeManager") -> None:
        self.dmm = degraded_mode_manager

    async def execute(self, duration_seconds: float) -> list[ChaosEvent]:
        """Force degraded mode.

        Validates: FallbackInferenceStrategy activates, confidence decays.
        """
        events: list[ChaosEvent] = []
        start = time.time()

        # Don't record any sensor readings — this triggers degradation
        await asyncio.sleep(min(duration_seconds, 5.0))

        status = self.dmm.get_degradation_status("chaos_degraded")

        events.append(ChaosEvent(
            event_type="degraded_runtime",
            triggered_at=start,
            payload={
                "is_degraded": status["is_degraded"],
                "confidence_multiplier": status["confidence_multiplier"],
                "using_fallback": status["using_fallback"],
            },
            expected_recovery_within_seconds=duration_seconds,
        ))

        logger.info("degraded_runtime_complete", status=status)
        return events
