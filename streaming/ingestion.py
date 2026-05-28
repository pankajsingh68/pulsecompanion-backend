"""Sensor ingestion pipeline — processes biometric snapshots through the full stack."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from events.event_models import EventType, SystemEvent
from utils.logger import get_logger

if TYPE_CHECKING:
    from baseline.baseline_store import BaselineStore
    from events.event_store import EventStore
    from human_state.engine import HumanStateEngine
    from orchestration.orchestrator import UXOrchestrator
    from reliability.signal_quality import SignalQualityAssessor
    from sensors.models import BiometricSnapshot
    from websocket.manager import ConnectionManager

logger = get_logger(__name__)


class SensorIngestionPipeline:
    """Accepts BiometricSnapshots, processes them through the full pipeline,
    emits WebSocket events WITHOUT requiring a chat message.

    Flow:
        BiometricSnapshot → reliability check → baseline update
        → human_state engine update → orchestration → WebSocket emit
    """

    def __init__(
        self,
        human_state_engine: "HumanStateEngine",
        orchestrator: "UXOrchestrator",
        ws_manager: "ConnectionManager",
        event_store: "EventStore",
        baseline_store: "BaselineStore",
        signal_quality_assessor: "SignalQualityAssessor",
    ) -> None:
        self.engine = human_state_engine
        self.orchestrator = orchestrator
        self.ws_manager = ws_manager
        self.event_store = event_store
        self.baseline_store = baseline_store
        self.quality = signal_quality_assessor
        self._prev_snapshots: dict[str, "BiometricSnapshot"] = {}

    async def ingest(
        self, session_id: str, snapshot: "BiometricSnapshot"
    ) -> None:
        """Process one biometric snapshot through the full pipeline.

        Args:
            session_id: The session this snapshot belongs to.
            snapshot: The biometric readings to process.
        """
        # Reliability check
        prev = self._prev_snapshots.get(session_id)
        reliability = self.quality.build_reliability_report(snapshot, prev)
        self._prev_snapshots[session_id] = snapshot

        # Skip if completely unreliable
        if reliability["overall_confidence"] < 0.2:
            logger.warning(
                "sensor_snapshot_rejected",
                session_id=session_id,
                reason="low_confidence",
            )
            return

        # Update baseline
        self.baseline_store.update_from_snapshot(session_id, snapshot)

        # Emit reliability warning if needed
        if reliability["warnings"]:
            await self.ws_manager.send_json(session_id, {
                "type": "reliability_warning",
                "warnings": reliability["warnings"],
                "session_id": session_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        # Update human state with new biometrics
        biometric_hint: dict = {}
        if snapshot.hr is not None:
            biometric_hint["hr"] = snapshot.hr
        if snapshot.hrv is not None:
            biometric_hint["hrv"] = snapshot.hrv

        rich_state = await self.engine.process(
            session_id=session_id,
            message="",  # no message — sensor-only update
            biometric_hint=biometric_hint if biometric_hint else None,
        )

        # Orchestrate
        strategy = await self.orchestrator.orchestrate(
            session_id, rich_state.model_dump()
        )

        # Emit state update via WebSocket
        await self.ws_manager.send_json(session_id, {
            "type": "sensor_state_update",
            "human_state": rich_state.to_legacy_human_state(),
            "ux_strategy": strategy.model_dump(mode="json"),
            "reliability": reliability,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # Store event
        self.event_store.append(SystemEvent(
            event_type=EventType.SENSOR_RECEIVED,
            session_id=session_id,
            payload={
                "hr": snapshot.hr,
                "hrv": snapshot.hrv,
                "confidence": reliability["overall_confidence"],
            },
        ))

        logger.info(
            "sensor_ingested",
            session_id=session_id,
            hr=snapshot.hr,
            hrv=snapshot.hrv,
            ux_mode=strategy.ux_mode,
        )
