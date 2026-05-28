"""Detects and records meaningful UX transitions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from orchestration.history.history_models import StrategyTransition

if TYPE_CHECKING:
    from orchestration.models import UXStrategy


class TransitionTracker:
    """Detects and records meaningful UX transitions.

    Ignores: no-op updates (same mode, same verbosity).
    Records: mode changes, verbosity jumps, tone shifts.
    """

    def is_meaningful_transition(
        self, prev: "UXStrategy", curr: "UXStrategy"
    ) -> bool:
        """Check if the transition between two strategies is meaningful."""
        if prev.ux_mode != curr.ux_mode:
            return True
        if prev.verbosity_level != curr.verbosity_level:
            return True
        if prev.response_tone != curr.response_tone:
            return True
        return False

    def build_transition(
        self,
        prev: "UXStrategy | None",
        curr: "UXStrategy",
        triggered_by: str = "chat_message",
    ) -> StrategyTransition:
        """Build a StrategyTransition record."""
        return StrategyTransition(
            session_id=curr.session_id,
            from_mode=prev.ux_mode if prev else None,
            to_mode=curr.ux_mode,
            timestamp=datetime.now(timezone.utc),
            reasoning=curr.reasoning,
            confidence=curr.confidence,
            triggered_by=triggered_by,
        )
