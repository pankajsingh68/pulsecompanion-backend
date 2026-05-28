"""Temporal adaptation — prevents jarring UX mode jumps between messages."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from utils.logger import get_logger

if TYPE_CHECKING:
    from orchestration.models import UXStrategy

logger = get_logger(__name__)


class TemporalAdaptation:
    """Smooths UX strategy transitions over time.

    Prevents: calm → overload_protection in a single message.
    Allows: gradual escalation and de-escalation.
    """

    MAX_VERBOSITY_JUMP = 1
    MODE_COOLDOWN_SECONDS = 15

    MODE_SEVERITY: dict[str, int] = {
        "normal": 0,
        "focus_mode": 1,
        "calm_minimal": 2,
        "overload_protection": 3,
    }

    def __init__(self) -> None:
        self._last_mode: str = "normal"
        self._last_change_time: datetime | None = None
        self._consecutive_count: int = 0

    def apply(
        self, proposed_strategy: "UXStrategy", prior_strategy: "UXStrategy | None"
    ) -> "UXStrategy":
        """Moderate proposed strategy to prevent jarring transitions.

        Args:
            proposed_strategy: The raw strategy from rule evaluation.
            prior_strategy: The previous strategy (if any).

        Returns:
            Potentially moderated UXStrategy with updated reasoning.
        """
        if prior_strategy is None:
            self._last_mode = proposed_strategy.ux_mode
            self._last_change_time = datetime.now(timezone.utc)
            return proposed_strategy

        current_mode = prior_strategy.ux_mode
        proposed_mode = proposed_strategy.ux_mode

        # Check cooldown
        now = datetime.now(timezone.utc)
        if self._last_change_time is not None:
            elapsed = (now - self._last_change_time).total_seconds()
            if elapsed < self.MODE_COOLDOWN_SECONDS and proposed_mode != current_mode:
                # Hold current mode
                proposed_strategy = proposed_strategy.model_copy(update={
                    "ux_mode": current_mode,
                    "reasoning": proposed_strategy.reasoning + [
                        f"mode cooldown active ({elapsed:.0f}s < {self.MODE_COOLDOWN_SECONDS}s)"
                    ],
                })
                return proposed_strategy

        # Cap mode severity jump
        capped_mode = self._cap_mode_transition(proposed_mode, current_mode)
        if capped_mode != proposed_mode:
            proposed_strategy = proposed_strategy.model_copy(update={
                "ux_mode": capped_mode,
                "reasoning": proposed_strategy.reasoning + [
                    f"gradual transition: {proposed_mode} capped to {capped_mode} from {current_mode}"
                ],
            })

        # Track mode changes
        if capped_mode != current_mode:
            self._last_mode = capped_mode
            self._last_change_time = now
            self._consecutive_count = 0
        else:
            self._consecutive_count += 1

        return proposed_strategy

    def _severity_of(self, mode: str) -> int:
        """Get severity level of a mode."""
        return self.MODE_SEVERITY.get(mode, 0)

    def _cap_mode_transition(self, proposed: str, current: str) -> str:
        """Cap mode transition to ±1 severity step."""
        proposed_sev = self._severity_of(proposed)
        current_sev = self._severity_of(current)

        if abs(proposed_sev - current_sev) <= 1:
            return proposed

        # Cap to ±1 step
        direction = 1 if proposed_sev > current_sev else -1
        capped_sev = current_sev + direction

        for mode, severity in self.MODE_SEVERITY.items():
            if severity == capped_sev:
                return mode

        return proposed
