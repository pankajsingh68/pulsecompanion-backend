"""Bounded strategy enforcer — clamps adaptation to safe limits."""

from __future__ import annotations

from typing import TYPE_CHECKING

from safety.adaptation_limits import (
    DEFAULT_BOUNDS,
    get_tone_index,
    get_verbosity_index,
    _VERBOSITY_ORDER,
    _TONE_ORDER,
)
from safety.safety_models import AdaptationBounds, SafetyGuardResult

if TYPE_CHECKING:
    from orchestration.models import UXStrategy


class BoundedStrategyEnforcer:
    """Applies AdaptationBounds to a proposed UXStrategy.

    Compares against prior strategy. Clamps any field that exceeds bounds.
    """

    def __init__(self, bounds: AdaptationBounds = DEFAULT_BOUNDS) -> None:
        self.bounds = bounds

    def enforce(
        self, proposed: "UXStrategy", prior: "UXStrategy | None"
    ) -> tuple["UXStrategy", SafetyGuardResult]:
        """Enforce bounds on proposed strategy.

        Returns:
            Tuple of (bounded_strategy, guard_result).
        """
        if prior is None:
            return proposed, SafetyGuardResult(was_limited=False)

        limited_fields: list[str] = []
        updates: dict = {}
        original = proposed.model_dump()

        # Verbosity bound
        curr_vi = get_verbosity_index(proposed.verbosity_level)
        prev_vi = get_verbosity_index(prior.verbosity_level)
        if abs(curr_vi - prev_vi) > self.bounds.max_verbosity_shift_per_turn:
            direction = 1 if curr_vi > prev_vi else -1
            capped_vi = prev_vi + direction * self.bounds.max_verbosity_shift_per_turn
            capped_vi = max(0, min(len(_VERBOSITY_ORDER) - 1, capped_vi))
            updates["verbosity_level"] = _VERBOSITY_ORDER[capped_vi]
            limited_fields.append("verbosity_level")

        # Tone bound
        curr_ti = get_tone_index(proposed.response_tone)
        prev_ti = get_tone_index(prior.response_tone)
        if abs(curr_ti - prev_ti) > self.bounds.max_tone_shift_per_turn:
            direction = 1 if curr_ti > prev_ti else -1
            capped_ti = prev_ti + direction * self.bounds.max_tone_shift_per_turn
            capped_ti = max(0, min(len(_TONE_ORDER) - 1, capped_ti))
            updates["response_tone"] = _TONE_ORDER[capped_ti]
            limited_fields.append("response_tone")

        # Emotional support delta bound
        delta = abs(
            proposed.emotional_support_level - prior.emotional_support_level
        )
        if delta > self.bounds.max_emotional_support_delta:
            direction = (
                1
                if proposed.emotional_support_level
                > prior.emotional_support_level
                else -1
            )
            capped = (
                prior.emotional_support_level
                + direction * self.bounds.max_emotional_support_delta
            )
            updates["emotional_support_level"] = max(0.0, min(1.0, capped))
            limited_fields.append("emotional_support_level")

        # Notification delay bound
        delay_delta = abs(
            proposed.notification_delay_seconds
            - prior.notification_delay_seconds
        )
        if delay_delta > self.bounds.max_notification_delay_jump:
            direction = (
                1
                if proposed.notification_delay_seconds
                > prior.notification_delay_seconds
                else -1
            )
            capped = (
                prior.notification_delay_seconds
                + direction * self.bounds.max_notification_delay_jump
            )
            updates["notification_delay_seconds"] = max(0, capped)
            limited_fields.append("notification_delay_seconds")

        was_limited = len(limited_fields) > 0

        if was_limited:
            reasoning = list(proposed.reasoning) if proposed.reasoning else []
            reasoning.append(
                f"adaptation bounded: {', '.join(limited_fields)} clamped"
            )
            updates["reasoning"] = reasoning

        bounded = proposed.model_copy(update=updates) if updates else proposed

        guard_result = SafetyGuardResult(
            was_limited=was_limited,
            original_strategy=original,
            limited_fields=limited_fields,
            reasoning=f"bounded {', '.join(limited_fields)}" if was_limited else "",
        )

        return bounded, guard_result
