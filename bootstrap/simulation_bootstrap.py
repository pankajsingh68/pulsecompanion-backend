"""Simulation bootstrap — only active when SIMULATION_ENABLED."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from utils.logger import get_logger

if TYPE_CHECKING:
    from bootstrap.dependency_registry import DependencyRegistry
    from bootstrap.observability_bootstrap import ObservabilityBundle
    from bootstrap.orchestration_bootstrap import OrchestrationBundle
    from bootstrap.streaming_bootstrap import StreamingBundle

logger = get_logger(__name__)


@dataclass
class SimulationBundle:
    """All simulation components as a typed bundle."""
    sensor_simulator: object
    session_simulator: object
    chaos_runner: object
    scenario_runner: object
    resilience_reporter: object
    playground: object


def bootstrap_simulation(
    registry: "DependencyRegistry",
    obs_bundle: "ObservabilityBundle",
    orch_bundle: "OrchestrationBundle",
    streaming_bundle: "StreamingBundle",
) -> SimulationBundle:
    """Initialize simulation layer. Only called when SIMULATION_ENABLED."""
    from simulation.sensor_simulator import SensorSimulator
    from simulation.session_simulator import SessionSimulator
    from simulation.runtime_scenario_runner import RuntimeScenarioRunner
    from simulation.orchestration_playground import OrchestrationPlayground
    from chaos.chaos_runner import ChaosRunner
    from metrics.resilience_reporter import ResilienceReporter

    sensor_sim = SensorSimulator(seed=42)
    session_sim = SessionSimulator(sensor_sim=sensor_sim)
    chaos_runner = ChaosRunner(registry=registry, metrics=obs_bundle.metrics, seed=42)
    scenario_runner = RuntimeScenarioRunner(session_sim, chaos_runner)
    resilience_reporter = ResilienceReporter()
    playground = OrchestrationPlayground(
        orchestrator=orch_bundle.orchestrator,
        confidence_engine=orch_bundle.confidence_engine,
        strategy_store=orch_bundle.strategy_store,
        state_timeline=streaming_bundle.state_timeline,
    )

    registry.register("sensor_simulator", sensor_sim)
    registry.register("session_simulator", session_sim)
    registry.register("chaos_runner", chaos_runner)
    registry.register("scenario_runner", scenario_runner)
    registry.register("resilience_reporter", resilience_reporter)
    registry.register("orchestration_playground", playground)

    bundle = SimulationBundle(
        sensor_simulator=sensor_sim,
        session_simulator=session_sim,
        chaos_runner=chaos_runner,
        scenario_runner=scenario_runner,
        resilience_reporter=resilience_reporter,
        playground=playground,
    )

    logger.info("subsystem_initialized", subsystem="simulation", component_count=6)
    return bundle
