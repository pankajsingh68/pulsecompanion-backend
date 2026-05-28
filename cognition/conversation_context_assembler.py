"""Conversation Context Assembler — emotionally selective continuity assembly.

Builds compact, emotionally-relevant LLM context from:
- Immediate conversational continuity (last 4 turns)
- Emotionally important moments (max 3)
- Longitudinal relationship summary

NOT chat history dumping. Emotionally selective and bounded.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from uuid import UUID

from cognition.context_priority_engine import ContextPriorityEngine
from cognition.context_summarizer import ContextSummarizer
from utils.logger import get_logger

if TYPE_CHECKING:
    from cognition.response_policy_engine import ResponsePolicy
    from emotion.relational_pattern_memory import RelationalPatternState

logger = get_logger(__name__)

# Token budgets (chars)
IMMEDIATE_BUDGET = 800
IMPORTANT_BUDGET = 600
LONGITUDINAL_BUDGET = 300
TOTAL_BUDGET = 2000


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


@dataclass(frozen=True)
class ConversationTurn:
    """Immutable conversation turn record."""
    role: str
    text: str
    emotional_weight: float
    timestamp: float
    response_mode: str
    stress_level: float
    was_interrupted: bool
    lineage_id: UUID | None = None


@dataclass(frozen=True)
class AssembledContext:
    """Output of context assembly."""
    context_text: str
    selected_turn_count: int
    important_memory_count: int
    context_budget_used: int
    truncated_turns: int
    longitudinal_included: bool


class ConversationContextAssembler:
    """Builds compact emotionally-relevant LLM context.

    Deterministic: same inputs → byte-identical output.
    Bounded: max 200 turns, 50 important moments, 20 summaries.
    """

    def __init__(self) -> None:
        self._turns: deque[ConversationTurn] = deque(maxlen=200)
        self._important_moments: deque[ConversationTurn] = deque(maxlen=50)
        self._priority = ContextPriorityEngine()
        self._summarizer = ContextSummarizer()
        self._diagnostics: deque[dict] = deque(maxlen=100)

    def add_turn(
        self,
        role: str,
        text: str,
        stress: float = 0.0,
        cognitive_load: float = 0.0,
        response_mode: str = "neutral",
        was_interrupted: bool = False,
        overload_active: bool = False,
        timestamp: float = 0.0,
        lineage_id: UUID | None = None,
    ) -> ConversationTurn:
        """Add a conversation turn. Computes emotional weight."""
        weight = self._compute_weight(
            stress, cognitive_load, was_interrupted, overload_active, response_mode
        )

        turn = ConversationTurn(
            role=role,
            text=text[:500],  # cap individual turn length
            emotional_weight=round(weight, 4),
            timestamp=timestamp,
            response_mode=response_mode,
            stress_level=round(stress, 4),
            was_interrupted=was_interrupted,
            lineage_id=lineage_id,
        )

        self._turns.append(turn)

        # Track important moments
        if weight > 0.75 or stress > 0.7 or overload_active:
            self._important_moments.append(turn)

        return turn

    def assemble(
        self,
        current_utterance: str,
        emotional_state: dict | None = None,
        pattern_state: "RelationalPatternState | None" = None,
        policy: "ResponsePolicy | None" = None,
    ) -> AssembledContext:
        """Assemble emotionally-selective context for LLM.

        Priority: current utterance > immediate > important > longitudinal > ordinary
        """
        emotional_state = emotional_state or {}
        truncated = 0

        # Layer 1: Immediate continuity (last 4 turns)
        recent = list(self._turns)[-4:]
        immediate_parts: list[str] = []
        for turn in recent:
            line = f"{turn.role}: {turn.text}"
            immediate_parts.append(line)

        immediate_text = "\n".join(immediate_parts)
        if len(immediate_text) > IMMEDIATE_BUDGET:
            # Truncate oldest first, preserve most recent
            while len(immediate_text) > IMMEDIATE_BUDGET and len(immediate_parts) > 1:
                immediate_parts.pop(0)
                truncated += 1
                immediate_text = "\n".join(immediate_parts)

        # Layer 2: Emotionally important moments (max 3, not in immediate)
        recent_ids = {id(t) for t in recent}
        important = [
            m for m in self._important_moments
            if id(m) not in recent_ids
        ][-3:]

        important_parts: list[str] = []
        for moment in important:
            line = f"[Earlier - {moment.role}, stress={moment.stress_level:.1f}]: {moment.text[:150]}"
            important_parts.append(line)

        important_text = "\n".join(important_parts)
        if len(important_text) > IMPORTANT_BUDGET:
            while len(important_text) > IMPORTANT_BUDGET and len(important_parts) > 1:
                important_parts.pop(0)
                important_text = "\n".join(important_parts)

        # Layer 3: Longitudinal summary
        longitudinal_text = ""
        if pattern_state is not None:
            longitudinal_text = self._summarizer.summarize_pattern(pattern_state)
            if len(longitudinal_text) > LONGITUDINAL_BUDGET:
                longitudinal_text = longitudinal_text[:LONGITUDINAL_BUDGET]

        # Assemble with current utterance always first
        parts: list[str] = []

        if current_utterance:
            parts.append(f"[Current] User: {current_utterance[:400]}")

        if immediate_text:
            parts.append(f"[Recent conversation]\n{immediate_text}")

        if important_text:
            parts.append(f"[Emotionally significant moments]\n{important_text}")

        if longitudinal_text:
            parts.append(f"[Relationship context]\n{longitudinal_text}")

        # Budget enforcement
        assembled = "\n\n".join(parts)
        if len(assembled) > TOTAL_BUDGET:
            # Priority: current > immediate > important > longitudinal
            assembled = self._priority.enforce_budget(
                current_utterance, immediate_text, important_text,
                longitudinal_text, TOTAL_BUDGET,
            )

        result = AssembledContext(
            context_text=assembled,
            selected_turn_count=len(recent),
            important_memory_count=len(important),
            context_budget_used=len(assembled),
            truncated_turns=truncated,
            longitudinal_included=bool(longitudinal_text),
        )

        self._diagnostics.append({
            "turns": result.selected_turn_count,
            "important": result.important_memory_count,
            "budget_used": result.context_budget_used,
            "truncated": result.truncated_turns,
        })

        return result

    def _compute_weight(
        self, stress: float, cognitive_load: float,
        was_interrupted: bool, overload_active: bool,
        response_mode: str,
    ) -> float:
        """Deterministic emotional weight scoring."""
        interruption_factor = 0.8 if was_interrupted else 0.0
        silence_weight = 0.3  # base silence contribution

        base = (
            stress * 0.4
            + cognitive_load * 0.3
            + interruption_factor * 0.2
            + silence_weight * 0.1
        )

        # Boosts
        if overload_active:
            base += 0.15
        if response_mode == "reflective":
            base += 0.1

        return _clamp(base)

    async def get_context_diagnostics(self) -> dict:
        """Introspection: context assembly diagnostics."""
        weights = [t.emotional_weight for t in self._turns]
        return {
            "total_turns_stored": len(self._turns),
            "important_moments_stored": len(self._important_moments),
            "recent_diagnostics": list(self._diagnostics)[-5:],
            "emotional_weight_distribution": {
                "min": round(min(weights), 3) if weights else 0,
                "max": round(max(weights), 3) if weights else 0,
                "avg": round(sum(weights) / len(weights), 3) if weights else 0,
            },
        }
