"""Transition guard — prevents dangerous transition patterns."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from orchestration.models import UXStrategy


class TransitionGuard:
    """Prevents specific dangerous transition patterns.

    Rules:
    - Never suggest break more than MAX_CONSECUTIVE times in a row
    - Never jump emotional_support from <0.3 to >0.8 in one turn
    - Never flip proactive_assistance on/off every turn (min 2-turn hold)
    """

    MAX_CONSECUTIVE_BREAKS = 2

    def __init__(self) -> None:
        self._break_suggestion_streak: dict[str, int] = {}
        self._proactive_history: dict[str, list[bool]] = {}

    def apply(
        self, strategy: "UXStrategy", session_id: str
    ) -> tuple["UXStrategy", list[str]]:
        """Apply transition guards.

        Returns:
            Tuple of (guarded_strategy, list_of_triggered_guards).
        """
        triggered: list[str] = []
        updates: dict = {}

        # Break suggestion streak guard
        if strategy.suggest_break:
            streak = self._break_suggestion_streak.get(session_id, 0) + 1
            self._break_suggestion_streak[session_id] = streak
            if streak > self.MAX_CONSECUTIVE_BREAKS:
                updates["suggest_break"] = False
                triggered.append(
                    f"break_suggestion_capped: {streak} consecutive (max {self.MAX_CONSECUTIVE_BREAKS})"
                )
        else:
            self._break_suggestion_streak[session_id] = 0

        # Proactive assistance flip-flop guard
        history = self._proactive_history.get(session_id, [])
        history.append(strategy.proactive_assistance)
        self._proactive_history[session_id] = history[-4:]  # keep last 4

        if len(history) >= 4:
            # Detect alternating pattern: T,F,T,F or F,T,F,T
            if (
                history[-1] != history[-2]
                and history[-2] != history[-3]
                and history[-3] != history[-4]
            ):
                # Force hold on current value
                updates["proactive_assistance"] = history[-2]
                triggered.append("proactive_assistance_flip_flop_blocked")

        if updates:
            reasoning = list(strategy.reasoning) if strategy.reasoning else []
            reasoning.extend(triggered)
            updates["reasoning"] = reasoning
            strategy = strategy.model_copy(update=updates)

        return strategy, triggered
