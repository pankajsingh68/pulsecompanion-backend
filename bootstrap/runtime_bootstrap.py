"""Runtime bootstrap — RuntimeManager, StreamScheduler, AdaptiveLoopController."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from utils.logger import get_logger

if TYPE_CHECKING:
    from bootstrap.dependency_registry import DependencyRegistry
    from bootstrap.orchestration_bootstrap import OrchestrationBundle
    from bootstrap.streaming_bootstrap import StreamingBundle
    from bootstrap.observability_bootstrap import ObservabilityBundle
    from websocket.manager import ConnectionManager

logger = get_logger(__name__)


@dataclass
class RuntimeBundle:
    """All runtime management components."""
    runtime_manager: object
    ambient_loop: object
    protection: object
    degradation: object
    device_coordinator: object


def bootstrap_runtime(
    registry: "DependencyRegistry",
    orchestration: "OrchestrationBundle",
    streaming: "StreamingBundle",
    ws_manager: "ConnectionManager",
    observability: "ObservabilityBundle",
) -> RuntimeBundle:
    """Initialize runtime manager, ambient loop, protection, degradation, devices."""
    from streaming.runtime_manager import RuntimeManager
    from streaming.ambient_loop import AmbientAwarenessLoop
    from streaming.protection import AdaptiveThrottler
    from streaming.degradation import DegradedModeManager
    from streaming.device_coordinator import DeviceCoordinator

    runtime_manager = RuntimeManager(
        ingestion_pipeline=streaming.ingestion_pipeline,
        orchestrator=orchestration.orchestrator,
        ws_manager=ws_manager,
        session_runtime=orchestration.session_runtime,
        debouncer=orchestration.debouncer,
        hysteresis=orchestration.hysteresis,
        latency_tracker=observability.latency_tracker,
    )

    ambient_loop = AmbientAwarenessLoop(
        state_timeline=streaming.state_timeline,
        event_store=streaming.event_store,
        recompute_engine=streaming.recompute_engine,
        ws_manager=ws_manager,
        transition_guard=orchestration.transition_guard,
    )

    protection = AdaptiveThrottler()
    degradation = DegradedModeManager()
    device_coordinator = DeviceCoordinator(ws_manager=ws_manager)

    registry.register("runtime_manager", runtime_manager)
    registry.register("ambient_loop", ambient_loop)
    registry.register("protection", protection)
    registry.register("degradation", degradation)
    registry.register("device_coordinator", device_coordinator)

    bundle = RuntimeBundle(
        runtime_manager=runtime_manager,
        ambient_loop=ambient_loop,
        protection=protection,
        degradation=degradation,
        device_coordinator=device_coordinator,
    )

    logger.info("subsystem_initialized", subsystem="runtime", component_count=5)
    return bundle
