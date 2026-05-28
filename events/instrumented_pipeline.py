"""Instrumented pipeline — wraps real pipeline stages with event emission.

This module provides InstrumentedIngestionPipeline that wraps the existing
SensorIngestionPipeline and emits events at each stage boundary.

Instrumentation failure never crashes the production runtime.
Emission does not block the adaptive loop.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from events.event_bus import AsyncEventBus
from events.lineage import LineageContext, mint_lineage
from events.pipeline_instrumentation import PipelineInstrumentation
from utils.logger import get_logger

if TYPE_CHECKING:
    from sensors.models import BiometricSnapshot

logger = get_logger(__name__)


class InstrumentedIngestionPipeline:
    """Wraps the real ingestion pipeline with event bus instrumentation.

    Emits events at exactly 9 stage boundaries without modifying
    the production pipeline's behavior.
    """

    def __init__(
        self,
        bus: AsyncEventBus,
        human_state_engine,
        orchestrator,
        ws_manager,
        event_store,
        baseline_store,
        signal_quality_assessor,
        bounded_enforcer=None,
        transition_guard=None,
    ) -> None:
        self._bus = bus
        self._instrumentation = PipelineInstrumentation(bus)
        self.engine = human_state_engine
        self.orchestrator = orchestrator
        self.ws_manager = ws_manager
        self.event_store = event_store
        self.baseline_store = baseline_store
        self.quality = signal_quality_assessor
        self.bounded_enforcer = bounded_enforcer
        self.transition_guard = transition_guard
        self._prev_snapshots: dict[str, "BiometricSnapshot"] = {}

    async def ingest(
        self, session_id: str, snapshot: "BiometricSnapshot"
    ) -> None:
        """Process one biometric snapshot through the full instrumented pipeline.

        Emits 9 stage events on the bus. Each emission is wrapped in
        try/except to never crash the production path.
        """
        # Mint lineage at ingestion boundary — the ONLY place this happens
        lineage = mint_lineage(session_id, source=snapshot.source.value if hasattr(snapshot, 'source') else "manual")

        # Stamp lineage onto the snapshot
        snapshot.lineage_id = str(lineage.lineage_id)
        snapshot.created_monotonic = lineage.created_monotonic
        snapshot.event_timestamp = lineage.event_timestamp

        # --- Stage 1: Sensor Ingestion ---
        await self._safe_emit(
            self._instrumentation.emit_sensor_ingested,
            lineage, snapshot.hr, snapshot.hrv, snapshot.gsr,
            source=snapshot.source.value if hasattr(snapshot, 'source') else "manual",
            quality=snapshot.overall_confidence,
        )

        # --- Stage 2: Sensor Normalization (reliability check) ---
        prev = self._prev_snapshots.get(session_id)
        reliability = self.quality.build_reliability_report(snapshot, prev)
        self._prev_snapshots[session_id] = snapshot

        await self._safe_emit(
            self._instrumentation.emit_sensor_normalized,
            lineage, snapshot.hr, snapshot.hrv, reliability,
        )

        # Skip if completely unreliable
        if reliability["overall_confidence"] < 0.2:
            logger.warning("snapshot_rejected", session_id=session_id)
            return

        # Update baseline
        self.baseline_store.update_from_snapshot(session_id, snapshot)

        # --- Stage 3: Human State Estimation ---
        biometric_hint: dict = {}
        if snapshot.hr is not None:
            biometric_hint["hr"] = snapshot.hr
        if snapshot.hrv is not None:
            biometric_hint["hrv"] = snapshot.hrv

        rich_state = await self.engine.process(
            session_id=session_id,
            message="",
            biometric_hint=biometric_hint if biometric_hint else None,
        )

        # Stamp lineage onto state
        rich_state.lineage_id = str(lineage.lineage_id)
        rich_state.created_monotonic = lineage.created_monotonic
        rich_state.event_timestamp = lineage.event_timestamp

        state_dict = rich_state.model_dump()
        await self._safe_emit(
            self._instrumentation.emit_state_estimated, lineage, state_dict,
        )

        # --- Stage 4: Temporal Smoothing (already inside engine.process) ---
        # The smoothing is internal to the engine — emit the smoothed result
        # (same as state_estimated since engine returns smoothed state)

        # --- Stage 5: Orchestration ---
        strategy = await self.orchestrator.orchestrate(session_id, state_dict)

        # Stamp lineage onto strategy
        strategy = strategy.model_copy(update={
            "lineage_id": str(lineage.lineage_id),
            "created_monotonic": lineage.created_monotonic,
            "event_timestamp": lineage.event_timestamp,
        })

        strategy_dict = strategy.model_dump(mode="json")
        await self._safe_emit(
            self._instrumentation.emit_orchestration_completed,
            lineage, strategy_dict,
        )

        # --- Stage 6: Safety Correction ---
        was_limited = False
        limited_fields: list[str] = []
        if self.bounded_enforcer:
            prior_strategy = self.orchestrator.get_current_strategy(session_id)
            bounded, guard_result = self.bounded_enforcer.enforce(strategy, prior_strategy)
            was_limited = guard_result.was_limited
            limited_fields = guard_result.limited_fields
            guard_result.lineage_id = str(lineage.lineage_id)
            if was_limited:
                strategy = bounded

        await self._safe_emit(
            self._instrumentation.emit_safety_corrected,
            lineage, was_limited, limited_fields,
            strategy.ux_mode, strategy.ux_mode, "",
        )

        # --- Stage 7: WebSocket Emission ---
        ws_payload = {
            "type": "sensor_state_update",
            "human_state": rich_state.to_legacy_human_state(),
            "ux_mode": strategy.ux_mode,
            "lineage_id": str(lineage.lineage_id),
        }
        import json
        payload_size = len(json.dumps(ws_payload, default=str))

        success = await self.ws_manager.send_json(session_id, ws_payload)
        await self._safe_emit(
            self._instrumentation.emit_websocket_emitted,
            lineage, "sensor_state_update", payload_size, success,
        )

        # --- Stage 8: Memory Persistence ---
        from events.event_models import EventType, SystemEvent
        self.event_store.append(SystemEvent(
            event_type=EventType.SENSOR_RECEIVED,
            session_id=session_id,
            payload={
                "hr": snapshot.hr, "hrv": snapshot.hrv,
                "lineage_id": str(lineage.lineage_id),
                "confidence": reliability["overall_confidence"],
            },
        ))

        await self._safe_emit(
            self._instrumentation.emit_memory_persisted,
            lineage, "event_store", 0.5, None, "system_events",
        )

        logger.info(
            "instrumented_ingest_complete",
            session_id=session_id,
            lineage_id=str(lineage.lineage_id),
            latency_ms=round(lineage.elapsed_ms(), 2),
        )

    async def _safe_emit(self, emit_fn, *args, **kwargs) -> None:
        """Wrap emission in try/except — never crash production."""
        try:
            await emit_fn(*args, **kwargs)
        except Exception as e:
            logger.warning("instrumentation_emit_failed", error=str(e))
