"""Queryable timeline over strategy history."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from orchestration.history.strategy_store import StrategyStore


class StrategyTimeline:
    """Queryable timeline over StrategyStore.

    Answers: how has UX mode evolved over this session?
    """

    def __init__(self, store: "StrategyStore") -> None:
        self.store = store

    def get_mode_history(self, session_id: str) -> list[str]:
        """Get sequence of UX modes for a session."""
        return [
            s.strategy.get("ux_mode", "normal")
            for s in self.store.get_history(session_id)
        ]

    def get_verbosity_trend(self, session_id: str) -> list[str]:
        """Get sequence of verbosity levels."""
        return [
            s.strategy.get("verbosity_level", "normal")
            for s in self.store.get_history(session_id)
        ]

    def count_mode_changes(self, session_id: str) -> int:
        """Count how many times the mode changed."""
        modes = self.get_mode_history(session_id)
        if len(modes) < 2:
            return 0
        return sum(1 for i in range(1, len(modes)) if modes[i] != modes[i - 1])

    def time_in_mode(self, session_id: str, mode: str) -> float:
        """Estimate seconds spent in a given mode."""
        history = self.store.get_history(session_id)
        total = 0.0
        for i, snap in enumerate(history):
            if snap.strategy.get("ux_mode") == mode:
                if i + 1 < len(history):
                    delta = (
                        history[i + 1].transition.timestamp
                        - snap.transition.timestamp
                    ).total_seconds()
                    total += max(0, delta)
                else:
                    total += 5.0  # assume 5s for latest
        return total
