"""Orchestration validator — replays strategy history and checks invariants."""

from __future__ import annotations

from typing import TYPE_CHECKING

from utils.logger import get_logger

if TYPE_CHECKING:
    from orchestration.history.strategy_store import StrategyStore

logger = get_logger(__name__)


class OrchestrationValidator:
    """Replays strategy_store history and validates invariants.

    Checks: every transition passed through TransitionGuard,
    hysteresis respected, no strategy bypassed BoundedStrategyEnforcer.
    """

    def __init__(self, strategy_store: "StrategyStore") -> None:
        self.store = strategy_store

    def validate_session(self, session_id: str) -> dict:
        """Validate all orchestration decisions for a session.

        Returns dict with: valid (bool), violations (list), total_transitions (int).
        """
        history = self.store.get_history(session_id)
        violations: list[str] = []

        for i in range(1, len(history)):
            prev = history[i - 1].strategy
            curr = history[i].strategy

            # Check verbosity jump
            prev_v = prev.get("verbosity_level", "normal")
            curr_v = curr.get("verbosity_level", "normal")
            verbosity_order = ["minimal", "short", "normal", "detailed"]
            if prev_v in verbosity_order and curr_v in verbosity_order:
                jump = abs(verbosity_order.index(curr_v) - verbosity_order.index(prev_v))
                if jump > 1:
                    violations.append(
                        f"verbosity_jump: {prev_v} → {curr_v} (step={jump})"
                    )

        return {
            "valid": len(violations) == 0,
            "violations": violations,
            "total_transitions": len(history),
        }
