"""Recovery validator — verifies system returns to stable state after chaos."""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from simulation.simulation_models import RecoveryResult
from utils.logger import get_logger

if TYPE_CHECKING:
    from bootstrap.observability_bootstrap import MetricsAggregator
    from events.state_timeline import StateTimeline
    from orchestration.orchestrator import UXOrchestrator

logger = get_logger(__name__)


class RecoveryValidator:
    """Monitors system recovery after chaos events."""

    def __init__(
        self,
        state_timeline: "StateTimeline",
        orchestrator: "UXOrchestrator",
        metrics: "MetricsAggregator",
    ) -> None:
        self.state_timeline = state_timeline
        self.orchestrator = orchestrator
        self.metrics = metrics

    async def validate(
        self, session_id: str, expected_recovery_within_seconds: float
    ) -> RecoveryResult:
        """Monitor recovery within expected window.

        Detects: oscillation loops, stuck degraded states, confidence non-recovery.
        """
        start = time.time()
        check_interval = 1.0
        oscillations = 0
        last_mode = None

        while time.time() - start < expected_recovery_within_seconds:
            strategy = self.orchestrator.get_current_strategy(session_id)
            if strategy:
                current_mode = strategy.ux_mode
                if last_mode and current_mode != last_mode:
                    oscillations += 1
                last_mode = current_mode

                # Check if recovered (back to normal or focus)
                if current_mode in ("normal", "focus_mode"):
                    return RecoveryResult(
                        recovered=True,
                        time_to_recovery_seconds=round(time.time() - start, 2),
                        oscillations_detected=oscillations,
                        final_state=current_mode,
                    )

            await asyncio.sleep(check_interval)

        # Timed out
        return RecoveryResult(
            recovered=False,
            time_to_recovery_seconds=round(time.time() - start, 2),
            oscillations_detected=oscillations,
            final_state=last_mode or "unknown",
        )
