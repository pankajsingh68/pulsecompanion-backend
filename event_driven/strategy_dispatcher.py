"""Central dispatch point for all orchestration recomputes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from event_driven.event_models import OrchestrationRequest
from orchestration.history.history_models import StrategySnapshot
from utils.logger import get_logger

if TYPE_CHECKING:
    from confidence.confidence_models import ModalityConfidence
    from confidence.modality_confidence import ModalityConfidenceEstimator
    from confidence.orchestration_confidence import OrchestrationConfidenceEngine
    from event_driven.orchestration_events import OrchestrationEventEmitter
    from orchestration.history.strategy_store import StrategyStore
    from orchestration.history.transition_tracker import TransitionTracker
    from orchestration.models import UXStrategy
    from orchestration.orchestrator import UXOrchestrator
    from runtime.session_runtime import SessionRuntime
    from safety.bounded_strategy import BoundedStrategyEnforcer
    from safety.transition_guard import TransitionGuard

logger = get_logger(__name__)


class StrategyDispatcher:
    """Central dispatch point for all orchestration recomputes.

    Flow per dispatch:
    1. Receive OrchestrationRequest
    2. Acquire session lock (via SessionRuntime)
    3. Run UXOrchestrator.orchestrate()
    4. Run confidence composition
    5. Apply safety bounds
    6. Apply transition guards
    7. Store in StrategyStore
    8. Emit WebSocket events
    9. Release lock
    """

    def __init__(
        self,
        orchestrator: "UXOrchestrator",
        confidence_engine: "OrchestrationConfidenceEngine",
        bounded_enforcer: "BoundedStrategyEnforcer",
        transition_guard: "TransitionGuard",
        strategy_store: "StrategyStore",
        event_emitter: "OrchestrationEventEmitter",
        session_runtime: "SessionRuntime",
    ) -> None:
        self.orchestrator = orchestrator
        self.confidence_engine = confidence_engine
        self.bounded_enforcer = bounded_enforcer
        self.transition_guard = transition_guard
        self.strategy_store = strategy_store
        self.event_emitter = event_emitter
        self.session_runtime = session_runtime

    async def dispatch(self, request: OrchestrationRequest) -> "UXStrategy":
        """Dispatch a full orchestration recompute.

        Args:
            request: The orchestration request with session and state info.

        Returns:
            The final bounded UXStrategy.
        """
        session_id = request.session_id

        async def _do_orchestrate():
            # 1. Run orchestrator
            strategy = await self.orchestrator.orchestrate(
                session_id, request.human_state
            )

            # 2. Compute confidence
            from confidence.confidence_models import ModalityConfidence

            modality_conf = ModalityConfidence(
                overall=request.reliability_report.get("overall_confidence", 1.0),
                hr_confidence=request.reliability_report.get("hr_confidence", 1.0),
                hrv_confidence=request.reliability_report.get("hrv_confidence", 1.0),
            )
            conf = self.confidence_engine.compute(
                modality_conf, [], request.metadata
            )

            # 3. Apply confidence weighting
            from confidence.reliability_weighting import apply_confidence_to_strategy

            strategy = apply_confidence_to_strategy(strategy, conf)

            # 4. Apply safety bounds
            prior = self.orchestrator.get_current_strategy(session_id)
            strategy, guard_result = self.bounded_enforcer.enforce(strategy, prior)

            # 5. Apply transition guards
            strategy, guard_triggers = self.transition_guard.apply(
                strategy, session_id
            )

            # 6. Store in history
            from orchestration.history.history_models import StrategyTransition

            transition = StrategyTransition(
                session_id=session_id,
                from_mode=prior.ux_mode if prior else None,
                to_mode=strategy.ux_mode,
                reasoning=strategy.reasoning,
                confidence=conf.composite,
                triggered_by=request.trigger.value,
            )
            snapshot = StrategySnapshot(
                strategy=strategy.model_dump(mode="json"),
                transition=transition,
                state_at_time=request.human_state,
            )
            self.strategy_store.append(session_id, snapshot)

            # 7. Emit events
            await self.event_emitter.emit_recompute(
                session_id, strategy, guard_result, conf
            )

            logger.info(
                "strategy_dispatched",
                session_id=session_id,
                trigger=request.trigger.value,
                ux_mode=strategy.ux_mode,
                confidence=round(conf.composite, 3),
                was_limited=guard_result.was_limited,
            )

            return strategy

        return await self.session_runtime.safe_update(
            session_id, _do_orchestrate
        )
