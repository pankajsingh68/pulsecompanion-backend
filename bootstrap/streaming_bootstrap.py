"""Streaming bootstrap — ingestion pipeline, stream manager, sync engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from utils.logger import get_logger

if TYPE_CHECKING:
    from bootstrap.dependency_registry import DependencyRegistry
    from bootstrap.observability_bootstrap import ObservabilityBundle
    from bootstrap.orchestration_bootstrap import OrchestrationBundle
    from websocket.manager import ConnectionManager

logger = get_logger(__name__)


@dataclass
class StreamingBundle:
    """All streaming infrastructure components."""
    ingestion_pipeline: object
    stream_manager: object
    sensor_normalizer: object
    baseline_store: object
    signal_quality: object
    event_store: object
    state_timeline: object
    behavioral_context: object
    temporal_context: object
    sync_engine: object
    recompute_engine: object


def bootstrap_streaming(
    registry: "DependencyRegistry",
    orchestration: "OrchestrationBundle",
    ws_manager: "ConnectionManager",
    observability: "ObservabilityBundle",
) -> StreamingBundle:
    """Initialize streaming, sync, and recompute components."""
    from sensors.normalizer import SensorNormalizer
    from baseline.baseline_store import BaselineStore
    from reliability.signal_quality import SignalQualityAssessor
    from events.event_store import EventStore
    from events.state_timeline import StateTimeline
    from context.behavioral_context import BehavioralContext
    from context.temporal_context import TemporalContext
    from streaming.ingestion import SensorIngestionPipeline
    from streaming.stream_manager import StreamManager
    from streaming.sync_engine import SyncEngine
    from streaming.recompute_engine import RecomputeEngine

    sensor_normalizer = SensorNormalizer()
    baseline_store = BaselineStore()
    signal_quality = SignalQualityAssessor()
    event_store = EventStore()
    state_timeline = StateTimeline()
    behavioral_context = BehavioralContext()
    temporal_context = TemporalContext()

    ingestion = SensorIngestionPipeline(
        human_state_engine=orchestration.human_state_engine,
        orchestrator=orchestration.orchestrator,
        ws_manager=ws_manager,
        event_store=event_store,
        baseline_store=baseline_store,
        signal_quality_assessor=signal_quality,
    )

    stream_manager = StreamManager(ingestion)
    sync_engine = SyncEngine()

    recompute_engine = RecomputeEngine(
        human_state_engine=orchestration.human_state_engine,
        orchestrator=orchestration.orchestrator,
        sync_engine=sync_engine,
        confidence_engine=orchestration.confidence_engine,
        bounded_enforcer=orchestration.bounded_enforcer,
        transition_guard=orchestration.transition_guard,
        strategy_store=orchestration.strategy_store,
        ws_manager=ws_manager,
        session_runtime=orchestration.session_runtime,
        latency_tracker=observability.latency_tracker,
    )

    # Register all
    registry.register("sensor_normalizer", sensor_normalizer)
    registry.register("baseline_store", baseline_store)
    registry.register("signal_quality", signal_quality)
    registry.register("event_store", event_store)
    registry.register("state_timeline", state_timeline)
    registry.register("behavioral_context", behavioral_context)
    registry.register("temporal_context", temporal_context)
    registry.register("ingestion_pipeline", ingestion)
    registry.register("stream_manager", stream_manager)
    registry.register("sync_engine", sync_engine)
    registry.register("recompute_engine", recompute_engine)

    bundle = StreamingBundle(
        ingestion_pipeline=ingestion, stream_manager=stream_manager,
        sensor_normalizer=sensor_normalizer, baseline_store=baseline_store,
        signal_quality=signal_quality, event_store=event_store,
        state_timeline=state_timeline, behavioral_context=behavioral_context,
        temporal_context=temporal_context, sync_engine=sync_engine,
        recompute_engine=recompute_engine,
    )

    logger.info("subsystem_initialized", subsystem="streaming", component_count=11)
    return bundle
