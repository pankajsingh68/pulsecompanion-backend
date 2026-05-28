"""Behavioral signal extraction — session patterns and typing behavior."""

from __future__ import annotations

from typing import TYPE_CHECKING

from utils.helpers import clamp

if TYPE_CHECKING:
    from human_state.models import RawSignals


class BehaviorSignalExtractor:
    """Extract signals from session behavioral patterns.

    Analyzes typing speed, message frequency, and session duration
    to infer cognitive load, engagement, and social energy.
    """

    def extract(self, raw: "RawSignals") -> dict:
        """Extract behavioral signals from raw session data.

        Args:
            raw: RawSignals container with behavioral context.

        Returns:
            Dict with keys: cognitive_load, engagement_from_length, social_energy.
        """
        scores: dict[str, float] = {}

        # Long messages = higher cognitive engagement
        if raw.message_word_count > 0:
            scores["engagement_from_length"] = clamp(
                raw.message_word_count / 80  # 80 words = fully engaged
            )

        # Many messages = higher social energy
        if raw.session_message_count > 0:
            scores["social_energy"] = clamp(
                raw.session_message_count / 20  # 20 messages = highly social
            )

        # Slow response = possible fatigue or cognitive load
        if raw.time_since_last_message_s is not None:
            delay = raw.time_since_last_message_s
            if delay > 120:  # > 2 min gap
                scores["cognitive_load_from_delay"] = 0.7
            elif delay > 60:
                scores["cognitive_load_from_delay"] = 0.4
            else:
                scores["cognitive_load_from_delay"] = 0.2

        # Combine cognitive load signals
        load_signals = [v for k, v in scores.items() if "cognitive_load" in k]
        if load_signals:
            scores["cognitive_load"] = clamp(
                sum(load_signals) / len(load_signals)
            )

        return scores
