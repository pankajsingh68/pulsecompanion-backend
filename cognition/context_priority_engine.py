"""Context Priority Engine — chooses what survives under context pressure.

Priority order:
1. Current user utterance (never dropped)
2. Immediate continuity
3. Emotional rupture moments
4. Longitudinal summary (never removed)
5. Low-emotional ordinary history (first to go)
"""

from __future__ import annotations

from utils.logger import get_logger

logger = get_logger(__name__)


class ContextPriorityEngine:
    """Enforces token budget by priority-based truncation.

    Current utterance and longitudinal summary are never removed.
    Oldest immediate turns are truncated first.
    """

    def enforce_budget(
        self,
        current_utterance: str,
        immediate_text: str,
        important_text: str,
        longitudinal_text: str,
        total_budget: int,
    ) -> str:
        """Assemble context within budget using priority rules.

        Priority: current > longitudinal > important > immediate
        (longitudinal is never removed; current is never removed)
        """
        # Always include current utterance
        current_block = f"[Current] User: {current_utterance[:400]}" if current_utterance else ""

        # Always include longitudinal (stable signal)
        longitudinal_block = f"[Relationship context]\n{longitudinal_text}" if longitudinal_text else ""

        # Fixed budget consumed
        fixed_used = len(current_block) + len(longitudinal_block) + 4  # separators
        remaining = total_budget - fixed_used

        # Fit important moments
        important_block = ""
        if important_text and remaining > 100:
            if len(important_text) <= remaining // 2:
                important_block = f"[Emotionally significant]\n{important_text}"
                remaining -= len(important_block) + 2
            else:
                # Truncate important to half remaining
                truncated = important_text[:remaining // 2]
                important_block = f"[Emotionally significant]\n{truncated}"
                remaining -= len(important_block) + 2

        # Fit immediate with whatever remains
        immediate_block = ""
        if immediate_text and remaining > 50:
            if len(immediate_text) <= remaining:
                immediate_block = f"[Recent]\n{immediate_text}"
            else:
                # Truncate from the beginning (oldest turns)
                lines = immediate_text.split("\n")
                while len("\n".join(lines)) > remaining and len(lines) > 1:
                    lines.pop(0)
                immediate_block = f"[Recent]\n{chr(10).join(lines)}"

        # Assemble in reading order
        parts = [p for p in [current_block, immediate_block, important_block, longitudinal_block] if p]
        return "\n\n".join(parts)
