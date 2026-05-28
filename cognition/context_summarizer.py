"""Context Summarizer — template-based deterministic summarization.

No generative summarization. No LLM calls. Template-based only.
Deterministic: same inputs → same output.
"""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

from utils.logger import get_logger

if TYPE_CHECKING:
    from emotion.relational_pattern_memory import RelationalPatternState

logger = get_logger(__name__)


class ContextSummarizer:
    """Compresses longitudinal state into natural language summaries.

    Template-based. Deterministic. No LLM summarization.
    """

    def __init__(self) -> None:
        self._summaries: deque[str] = deque(maxlen=20)

    def summarize_pattern(self, pattern: "RelationalPatternState") -> str:
        """Generate deterministic summary from RelationalPatternState."""
        phrases: list[str] = []

        # Stress baseline
        if pattern.stress_baseline > 0.65:
            phrases.append("The person has recently been carrying significant stress.")
        elif pattern.stress_baseline < 0.3:
            phrases.append("They have generally been calm across recent interactions.")

        # Overload frequency
        if pattern.overload_frequency > 0.5:
            phrases.append("They often feel overwhelmed during conversations.")
        elif pattern.overload_frequency > 0.3:
            phrases.append("They occasionally experience conversational overload.")

        # Recovery trend
        if pattern.recovery_trend > 0.4:
            phrases.append("They have been gradually recovering and opening up.")
        elif pattern.recovery_trend < -0.3:
            phrases.append("Recovery has been slow. Extra patience is warranted.")

        # Trust
        if pattern.trust_stability > 0.7:
            phrases.append("There is established conversational trust.")
        elif pattern.trust_stability < 0.4:
            phrases.append("Trust is still developing. Careful pacing needed.")

        # Engagement
        if pattern.engagement_baseline > 0.7:
            phrases.append("They tend to be actively engaged when present.")
        elif pattern.engagement_baseline < 0.3:
            phrases.append("They have been somewhat withdrawn or distant.")

        if not phrases:
            summary = "The person seems in a balanced state across sessions."
        else:
            summary = " ".join(phrases[:3])  # max 3 sentences

        self._summaries.append(summary)
        return summary

    def summarize_recent_trajectory(
        self, stress_trend: list[float], engagement_trend: list[float]
    ) -> str:
        """Summarize recent emotional trajectory from trends."""
        if not stress_trend:
            return ""

        # Stress direction
        if len(stress_trend) >= 3:
            if stress_trend[-1] > stress_trend[0] + 0.15:
                return "Stress has been rising across recent interactions."
            elif stress_trend[-1] < stress_trend[0] - 0.15:
                return "Stress has been declining. They may be settling."

        return ""
