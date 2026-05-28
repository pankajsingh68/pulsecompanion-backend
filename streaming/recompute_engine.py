"""Recompute engine — adaptive state recomputation from sensor streams."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from utils.logger import get_logger

if TYPE_CHECKING:
    from bootstrap.observability_bootstrap import LatencyTracker
    from confidence.orchestration_confidence import OrchestrationConfidenceEngine
    from human_state.engine import HumanStateEngine
    from orchestration.history.strategy_store import StrategyStore
    from orchestration.orchestrator import UXOrchestrator
    from runtime.session_runtime import SessionRuntime
    from safety.bounded_strategy import BoundedStrategyEnforcer
    from safety.transition_guard import TransitionGuard
    from streaming.sync_engine import SyncEngine
    from websocket.manager import ConnectionManager

logger = get_logger(__name__)


class RecomputePolicy:
    """Determines when a recompute is warranted."""

    def __init__(self, min_interval_s: float = 3.0) -> None:
        self.min_interval_s = min_interval_s
        self._last_recompute: dict[str, datetime] = {}

    def should_recompute(self, session_id: str) -> bool:
        last = self._last_recompute.get(session_id)
        if last is None:
            return True
        elapsed = (datetime.now(timezone.utc) - last).total_seconds()
        return elapsed >= self.min_interval_s

    def mark_recomputed(self, session_id: str) -> None:
        self._last_recompute[session_id] = datetime.now(timezone.utc)


class IncrementalStateUpdater:
    """Updates state incrementally from new sensor data without full recompute."""

    def should_full_recompute(self, delta: dict) -> bool:
        """If delta is large enough, trigger full recompute."""
        hr_delta = abs(delta.get("hr_delta", 0))
        hrv_delta = abs(delta.get("hrv_delta", 0))
        return hr_delta > 15 or hrv_delta > 10


class AdaptiveRecomputeScheduler:
    """Adjusts recompute frequency based on state volatility."""

    def __init__(self) -> None:
        self._intervals: dict[str, float] = {}

    def get_interval(self, session_id: str, stability_score: float) -> float:
        """Lower stability → more frequent recomputes."""
        if stability_score > 0.8:
            return 5.0
        if stability_score > 0.5:
            return 3.0
        return 1.5


class RecomputeEngine:
    """Wires recompute policy, state engine, orchestrator, and safety."""

    def __init__(
        self,
        human_state_engine: "HumanStateEngine",
        orchestrator: "UXOrchestrator",
        sync_engine: "SyncEngine",
        confidence_engine: "OrchestrationConfidenceEngine",
        bounded_enforcer: "BoundedStrategyEnforcer",
        transition_guard: "TransitionGuard",
        strategy_store: "StrategyStore",
        ws_manager: "ConnectionManager",
        session_runtime: "SessionRuntime",
        latency_tracker: "LatencyTracker",
    ) -> None:
        self.engine = human_state_engine
        self.orchestrator = orchestrator
        self.sync_engine = sync_engine
        self.confidence_engine = confidence_engine
        self.bounded_enforcer = bounded_enforcer
        self.transition_guard = transition_guard
        self.strategy_store = strategy_store
        self.ws_manager = ws_manager
        self.session_runtime = session_runtime
        self.latency_tracker = latency_tracker
        self.policy = RecomputePolicy()
        self.incremental = IncrementalStateUpdater()
        self.scheduler = AdaptiveRecomputeScheduler()

    async def recompute(self, session_id: str, biometric_hint: dict | None = None) -> dict | None:
        """Run a full recompute cycle for a session.

        Returns the computed strategy dict, or None if skipped.
        """
        if not self.policy.should_recompute(session_id):
            return None

        start = datetime.now(timezone.utc)

        # Get merged snapshot from sync engine
        merged = self.sync_engine.get_merged_snapshot(session_id)
        hint = biometric_hint or merged or None

        # Run state engine
        rich_state = await self.engine.process(
            session_id=session_id,
            message="",
            biometric_hint=hint,
        )

        # Run orchestrator
        strategy = await self.orchestrator.orchestrate(
            session_id, rich_state.model_dump()
        )

        self.policy.mark_recomputed(session_id)

        elapsed_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000
        self.latency_tracker.record("recompute", elapsed_ms)

        logger.debug(
            "recompute_complete",
            session_id=session_id,
            latency_ms=round(elapsed_ms, 2),
            ux_mode=strategy.ux_mode,
        )

        return strategy.model_dump(mode="json")
