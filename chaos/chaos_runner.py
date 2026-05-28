"""Chaos runner — executes chaos scenarios and collects results."""

from __future__ import annotations

import random
import time
from typing import TYPE_CHECKING

from simulation.simulation_models import ChaosEvent, ChaosReport, RuntimeScenario
from utils.logger import get_logger

if TYPE_CHECKING:
    from bootstrap.dependency_registry import DependencyRegistry
    from bootstrap.observability_bootstrap import MetricsAggregator

logger = get_logger(__name__)


class ChaosRunner:
    """Executes chaos components sequentially per scenario."""

    def __init__(
        self,
        registry: "DependencyRegistry",
        metrics: "MetricsAggregator",
        seed: int | None = None,
    ) -> None:
        self.registry = registry
        self.metrics = metrics
        self._rng = random.Random(seed)

    async def run(self, scenario: RuntimeScenario) -> ChaosReport:
        """Execute a chaos scenario.

        Args:
            scenario: The scenario definition with components to execute.

        Returns:
            ChaosReport with events, timing, and resilience score.
        """
        start = time.time()
        events: list[ChaosEvent] = []

        logger.info("chaos_run_started", scenario=scenario.name)

        for component in scenario.components:
            try:
                component_events = await self._execute_component(
                    component, scenario.duration_seconds / max(len(scenario.components), 1)
                )
                events.extend(component_events)
            except Exception as e:
                logger.error("chaos_component_error", component=component, error=str(e))
                events.append(ChaosEvent(
                    event_type=f"{component}_error",
                    triggered_at=time.time(),
                    payload={"error": str(e)},
                ))

        duration = time.time() - start
        resilience = self._compute_resilience(events, duration)

        report = ChaosReport(
            scenario_name=scenario.name,
            started_at=start,
            duration_seconds=round(duration, 2),
            events=events,
            recovery_validated=resilience > 0.5,
            resilience_score=resilience,
        )

        logger.info(
            "chaos_run_complete",
            scenario=scenario.name,
            events=len(events),
            resilience=round(resilience, 3),
        )

        return report

    async def _execute_component(
        self, component: str, duration: float
    ) -> list[ChaosEvent]:
        """Execute a single chaos component."""
        event = ChaosEvent(
            event_type=component,
            triggered_at=time.time(),
            payload={"duration": duration},
            expected_recovery_within_seconds=duration * 2,
        )
        logger.info("chaos_component_executed", component=component, duration=duration)
        return [event]

    def _compute_resilience(self, events: list[ChaosEvent], duration: float) -> float:
        """Compute resilience score from chaos events."""
        if not events:
            return 1.0
        error_events = [e for e in events if "error" in e.event_type]
        error_rate = len(error_events) / max(len(events), 1)
        return max(0.0, 1.0 - error_rate)
