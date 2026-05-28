"""Orchestration bootstrap — state engine, orchestrator, confidence, safety."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from utils.logger import get_logger

if TYPE_CHECKING:
    from bootstrap.dependency_registry import DependencyRegistry
    from bootstrap.observability_bootstrap import ObservabilityBundle

logger = get_logger(__name__)


@dataclass
class OrchestrationBundle:
    """All orchestration-layer components."""
    human_state_engine: object
    orchestrator: object
    confidence_engine: object
    modality_confidence: object
    bounded_enforcer: object
    transition_guard: object
    strategy_store: object
    transition_tracker: object
    session_runtime: object
    lock_manager: object
    event_queue: object
    debouncer: object
    hysteresis: object
    cooldowns: object
    batcher: object
    ws_throttle: object
    orchestration_trace: object
    state_inspector: object
    actor_registry: object
    event_router: object


def bootstrap_orchestration(
    registry: "DependencyRegistry",
    observability: "ObservabilityBundle",
) -> OrchestrationBundle:
    """Initialize all orchestration, confidence, safety, and runtime components."""
    from human_state.engine import HumanStateEngine
    from orchestration.orchestrator import UXOrchestrator
    from confidence.modality_confidence import ModalityConfidenceEstimator
    from confidence.orchestration_confidence import OrchestrationConfidenceEngine
    from safety.bounded_strategy import BoundedStrategyEnforcer
    from safety.transition_guard import TransitionGuard
    from orchestration.history.strategy_store import StrategyStore
    from orchestration.history.transition_tracker import TransitionTracker
    from runtime.session_lock_manager import SessionLockManager
    from runtime.event_queue import SessionEventQueue
    from runtime.session_runtime import SessionRuntime
    from stability.debounce import OrchestratorDebouncer
    from stability.hysteresis import ModeHysteresis
    from stability.cooldowns import CooldownManager
    from stability.batching import EventBatcher
    from stability.throttling import WebSocketThrottle
    from debug.orchestration_trace import OrchestrationTrace
    from debug.state_inspector import StateInspector
    from actors.actor_registry import ActorRegistry
    from event_driven.event_router import EventRouter

    engine = HumanStateEngine()
    orchestrator = UXOrchestrator()
    confidence_engine = OrchestrationConfidenceEngine()
    modality_confidence = ModalityConfidenceEstimator()
    bounded_enforcer = BoundedStrategyEnforcer()
    transition_guard = TransitionGuard()
    strategy_store = StrategyStore()
    transition_tracker = TransitionTracker()
    lock_manager = SessionLockManager()
    event_queue = SessionEventQueue()
    session_runtime = SessionRuntime(lock_manager=lock_manager, event_queue=event_queue)
    debouncer = OrchestratorDebouncer()
    hysteresis = ModeHysteresis()
    cooldowns = CooldownManager()
    batcher = EventBatcher()
    ws_throttle = WebSocketThrottle()
    orchestration_trace = OrchestrationTrace()
    state_inspector = StateInspector()
    actor_registry = ActorRegistry()
    event_router = EventRouter()

    # Register all
    registry.register("human_state_engine", engine)
    registry.register("orchestrator", orchestrator)
    registry.register("confidence_engine", confidence_engine)
    registry.register("modality_confidence", modality_confidence)
    registry.register("bounded_enforcer", bounded_enforcer)
    registry.register("transition_guard", transition_guard)
    registry.register("strategy_store", strategy_store)
    registry.register("transition_tracker", transition_tracker)
    registry.register("lock_manager", lock_manager)
    registry.register("event_queue", event_queue)
    registry.register("session_runtime", session_runtime)
    registry.register("debouncer", debouncer)
    registry.register("hysteresis", hysteresis)
    registry.register("cooldowns", cooldowns)
    registry.register("batcher", batcher)
    registry.register("ws_throttle", ws_throttle)
    registry.register("orchestration_trace", orchestration_trace)
    registry.register("state_inspector", state_inspector)
    registry.register("actor_registry", actor_registry)
    registry.register("event_router", event_router)

    bundle = OrchestrationBundle(
        human_state_engine=engine, orchestrator=orchestrator,
        confidence_engine=confidence_engine, modality_confidence=modality_confidence,
        bounded_enforcer=bounded_enforcer, transition_guard=transition_guard,
        strategy_store=strategy_store, transition_tracker=transition_tracker,
        session_runtime=session_runtime, lock_manager=lock_manager,
        event_queue=event_queue, debouncer=debouncer, hysteresis=hysteresis,
        cooldowns=cooldowns, batcher=batcher, ws_throttle=ws_throttle,
        orchestration_trace=orchestration_trace, state_inspector=state_inspector,
        actor_registry=actor_registry, event_router=event_router,
    )

    logger.info("subsystem_initialized", subsystem="orchestration", component_count=20)
    return bundle
