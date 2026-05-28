"""Orchestration event emitter — emits structured WebSocket events."""

from __future__ import annotations

from typing import TYPE_CHECKING

from utils.logger import get_logger

if TYPE_CHECKING:
    from confidence.confidence_models import OrchestrationConfidence
    from orchestration.models import UXStrategy
    from safety.safety_models import SafetyGuardResult
    from websocket.manager import ConnectionManager

logger = get_logger(__name__)


class OrchestrationEventEmitter:
    """Emits structured WebSocket events after each orchestration recompute."""

    def __init__(self, ws_manager: "ConnectionManager") -> None:
        self.ws_manager = ws_manager

    async def emit_recompute(
        self,
        session_id: str,
        strategy: "UXStrategy",
        guard_result: "SafetyGuardResult",
        conf: "OrchestrationConfidence",
    ) -> None:
        """Emit events after orchestration recompute.

        Events emitted:
        - orchestration_recomputed (always)
        - adaptation_limited (if safety guard fired)
        - confidence_drop (if confidence < 0.4)
        """
        from websocket.events import orchestration_recomputed_event

        await self.ws_manager.send_json(
            session_id,
            orchestration_recomputed_event(
                session_id=session_id,
                trigger="recompute",
                strategy_dict=strategy.model_dump(mode="json"),
                confidence=conf.composite,
            ),
        )

        if guard_result.was_limited:
            from websocket.events import adaptation_limited_event

            await self.ws_manager.send_json(
                session_id,
                adaptation_limited_event(
                    session_id=session_id,
                    limited_fields=guard_result.limited_fields,
                    guard_reason=guard_result.reasoning,
                ),
            )

        if conf.composite < 0.4:
            from websocket.events import confidence_drop_event

            await self.ws_manager.send_json(
                session_id,
                confidence_drop_event(
                    session_id=session_id,
                    composite_conf=conf.composite,
                    modality_report=conf.modality.model_dump(),
                ),
            )
