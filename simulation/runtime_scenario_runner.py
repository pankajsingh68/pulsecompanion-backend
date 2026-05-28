"""Runtime scenario runner — executes named chaos scenarios."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from simulation.simulation_models import RuntimeScenario, ScenarioResult
from utils.logger import get_logger

if TYPE_CHECKING:
    from chaos.chaos_runner import ChaosRunner
    from simulation.session_simulator import SessionSimulator

logger = get_logger(__name__)


class RuntimeScenarioRunner:
    """Executes named scenarios sequentially with proper timing."""

    def __init__(
        self,
        session_simulator: "SessionSimulator",
        chaos_runner: "ChaosRunner",
    ) -> None:
        self.session_simulator = session_simulator
        self.chaos_runner = chaos_runner

    async def run_scenario(self, scenario: RuntimeScenario) -> ScenarioResult:
        """Execute a complete runtime scenario.

        Args:
            scenario: The scenario definition.

        Returns:
            ScenarioResult with pass/fail, duration, events, metrics.
        """
        start = time.time()
        errors: list[str] = []
        events_triggered = 0

        logger.info(
            "scenario_started",
            name=scenario.name,
            components=scenario.components,
        )

        try:
            report = await self.chaos_runner.run(scenario)
            events_triggered = len(report.events)
        except Exception as e:
            errors.append(str(e))
            logger.error("scenario_error", name=scenario.name, error=str(e))

        duration = time.time() - start

        result = ScenarioResult(
            passed=len(errors) == 0,
            duration_seconds=round(duration, 2),
            events_triggered=events_triggered,
            errors=errors,
        )

        logger.info(
            "scenario_complete",
            name=scenario.name,
            passed=result.passed,
            duration=result.duration_seconds,
        )

        return result
