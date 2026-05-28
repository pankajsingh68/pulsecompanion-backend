"""Prompt Conditioner — translates ResponsePolicy into precise LLM system prompt.

The LLM receives behavioral instructions, not raw emotional data.
No floats in the prompt. Deterministic output.
Block 5: longitudinal emotional pattern summary from RelationalPatternState.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING

from cognition.response_policy_engine import ResponsePolicy
from emotion.emotional_intelligence_core import CycleOutput
from utils.logger import get_logger

if TYPE_CHECKING:
    from emotion.relational_pattern_memory import RelationalPatternState

logger = get_logger(__name__)

PROMPT_VERSION = 2  # incremented: Block 5 longitudinal summary added

# Block 1 — Identity anchor (static)
_IDENTITY = (
    "You are a calm, emotionally aware conversational companion. "
    "You adapt to the person's current state. You never overreact. "
    "You speak naturally, briefly, and with care."
)

# Block 2 — Mode instructions
_MODE_INSTRUCTIONS = {
    "minimal": "The person needs very little right now. One short sentence only. No questions. Pure acknowledgment.",
    "grounding": "The person is under stress. Speak slowly and calmly. No advice. No questions. Anchor them.",
    "supportive": "The person needs warmth. Be gentle. One soft question at most. Keep it brief.",
    "reflective": "The person is open. Reflect what they said. Ask one curious question.",
    "practical": "The person wants help. Be concrete and focused. Offer one clear suggestion.",
    "neutral": "Respond naturally and helpfully. Keep it conversational.",
}

# Max total prompt chars (~400 tokens)
_MAX_PROMPT_CHARS = 1600


@dataclass(frozen=True)
class ConditionedPrompt:
    system_prompt: str
    behavioral_constraints: str
    response_mode: str
    max_sentences: int
    max_questions: int
    pacing_density: str
    prompt_version: int


class PromptConditioner:
    """Builds deterministic LLM prompts from ResponsePolicy + CycleOutput.

    Accepts optional RelationalPatternState for Block 5 longitudinal summary.
    """

    def __init__(self) -> None:
        self._cache: deque[tuple] = deque(maxlen=20)
        self._output: ConditionedPrompt | None = None
        self._longitudinal_populated: bool = False
        self._longitudinal_phrases: list[str] = []

    def build(
        self,
        policy: ResponsePolicy,
        cycle_output: CycleOutput,
        pattern: "RelationalPatternState | None" = None,
    ) -> ConditionedPrompt:
        """Build ConditionedPrompt. Deterministic: same inputs → same output.

        Args:
            policy: Current response policy.
            cycle_output: Current emotional intelligence cycle output.
            pattern: Optional longitudinal pattern state for Block 5.
        """
        # Block 2
        mode_instruction = _MODE_INSTRUCTIONS.get(
            policy.response_mode, _MODE_INSTRUCTIONS["neutral"]
        )

        # Block 3 — Behavioral constraints
        constraints: list[str] = []
        if not policy.allow_reflection:
            constraints.append("Do not repeat the person's words back to them.")
        if not policy.allow_encouragement:
            constraints.append("Do not offer encouragement or positive affirmations.")
        if not policy.allow_practical_help:
            constraints.append("Do not offer advice or suggestions.")
        if policy.max_questions == 0:
            constraints.append("Do not ask any questions.")
        if policy.pacing_density == "sparse":
            constraints.append("Use simple words. Short sentences. Wide gaps between ideas.")

        behavioral_constraints = " ".join(constraints)

        # Block 4 — Emotional state summary (natural language, no floats)
        emotional_summary = self._emotional_to_natural(cycle_output)

        # Block 5 — Longitudinal pattern summary
        block5 = self._build_longitudinal_block(pattern)

        # Assemble prompt
        system_prompt = f"{_IDENTITY}\n\n{mode_instruction}\n\n{emotional_summary}"

        # If Block 5 would push over limit: truncate Block 4 first, never Block 5
        if block5:
            remaining_budget = _MAX_PROMPT_CHARS - len(_IDENTITY) - len(mode_instruction) - len(block5) - 12  # newlines
            if len(emotional_summary) > remaining_budget and remaining_budget > 0:
                emotional_summary = emotional_summary[:remaining_budget]
            system_prompt = f"{_IDENTITY}\n\n{mode_instruction}\n\n{emotional_summary}\n\n{block5}"

        # Final length enforcement
        if len(system_prompt) > _MAX_PROMPT_CHARS:
            system_prompt = system_prompt[:_MAX_PROMPT_CHARS]

        self._output = ConditionedPrompt(
            system_prompt=system_prompt,
            behavioral_constraints=behavioral_constraints,
            response_mode=policy.response_mode,
            max_sentences=policy.max_sentences,
            max_questions=policy.max_questions,
            pacing_density=policy.pacing_density,
            prompt_version=PROMPT_VERSION,
        )
        return self._output

    def _build_longitudinal_block(
        self, pattern: "RelationalPatternState | None"
    ) -> str:
        """Build Block 5 from RelationalPatternState. Deterministic.

        Returns empty string when pattern is None.
        Max 3 sentences. No floats. Natural language only.
        """
        self._longitudinal_populated = False
        self._longitudinal_phrases = []

        if pattern is None:
            return ""

        phrases: list[str] = []

        # Stress baseline
        if pattern.stress_baseline > 0.65:
            phrases.append(
                "This person tends to carry significant stress. "
                "Keep responses brief and gentle."
            )
        elif pattern.stress_baseline < 0.35:
            phrases.append(
                "This person is generally calm. Normal pacing is appropriate."
            )

        # Overload frequency
        if pattern.overload_frequency > 0.5:
            phrases.append(
                "They often feel overwhelmed in conversations. "
                "Err on the side of saying less."
            )

        # Recovery trend
        if pattern.recovery_trend > 0.4:
            phrases.append(
                "They have been recovering well recently. "
                "Slightly warmer tone is appropriate."
            )
        elif pattern.recovery_trend < -0.3:
            phrases.append(
                "Recovery has been slow. Extra patience and space."
            )

        # Trust stability
        if pattern.trust_stability < 0.4:
            phrases.append(
                "Trust is still building. Avoid probing questions."
            )
        elif pattern.trust_stability > 0.7:
            phrases.append(
                "There is good conversational trust. "
                "Gentle curiosity is welcome."
            )

        if not phrases:
            return ""

        # Max 3 sentences
        phrases = phrases[:3]
        self._longitudinal_populated = True
        self._longitudinal_phrases = list(phrases)

        return " ".join(phrases)

    def _emotional_to_natural(self, cycle_output: CycleOutput) -> str:
        """Translate emotional state to natural language. No floats."""
        es = cycle_output.emotional_state
        phrases: list[str] = []

        if es.stress > 0.7:
            phrases.append("The person appears quite stressed right now.")
        elif es.stress > 0.5:
            phrases.append("The person seems somewhat tense.")

        if es.cognitive_load > 0.7:
            phrases.append("They seem mentally overloaded.")
        elif es.cognitive_load > 0.5:
            phrases.append("They appear to be thinking hard.")

        if es.recovery_state > 0.6:
            phrases.append("They may be starting to settle.")

        if es.engagement < 0.3:
            phrases.append("They seem withdrawn or distant.")
        elif es.engagement > 0.7:
            phrases.append("They seem engaged and present.")

        return " ".join(phrases) if phrases else "The person seems in a balanced state."

    async def get_current_prompt(self) -> ConditionedPrompt | None:
        return self._output

    async def get_prompt_diagnostics(self) -> dict:
        """Prompt diagnostics including longitudinal block status."""
        return {
            "longitudinal_block_populated": self._longitudinal_populated,
            "longitudinal_phrases_used": list(self._longitudinal_phrases),
            "prompt_version": PROMPT_VERSION,
        }
