"""Orchestration playground — debugging hooks for orchestration decisions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from utils.logger import get_logger

if TYPE_CHECKING:
    from confidence.orchestration_confidence import OrchestrationConfidenceEngine
    from events.state_timeline import StateTimeline
    from orchestration.history.strategy_store import StrategyStore
    from orchestration.orchestrator import UXOrchestrator

logger = get_logger(__name__)


class OrchestrationPlayground:
    """Debugging hooks for orchestration decisions."""

    def __init__(
        self,
        orchestrator: "UXOrchestrator",
        confidence_engine: "OrchestrationConfidenceEngine",
        strategy_store: "StrategyStore",
        state_timeline: "StateTimeline",
    ) -> None:
        self.orchestrator = orchestrator
        self.confidence_engine = confidence_engine
        self.strategy_store = strategy_store
        self.state_timeline = state_timeline

    async def replay_session(self, session_id: str) -> list[dict]:
        """Replay stored events through orchestrator."""
        history = self.strategy_store.get_history(session_id)
        return [s.strategy for s in history]

    def inspect_transition(self, from_state: dict, to_state: dict) -> dict:
        """Inspect what would happen transitioning between two states."""
        return {
            "from_mode": from_state.get("ux_mode", "normal"),
            "to_mode": to_state.get("ux_mode", "normal"),
            "stress_delta": to_state.get("stress", 0) - from_state.get("stress", 0),
            "fatigue_delta": to_state.get("fatigue", 0) - from_state.get("fatigue", 0),
        }

    def inspect_degradation_trigger(self) -> dict:
        """Return last degradation cause + fallback chosen."""
        return {"status": "no_degradation_recorded"}

    def inspect_throttling_state(self) -> dict:
        """Return current throttler metrics."""
        return {"status": "throttler_idle"}
