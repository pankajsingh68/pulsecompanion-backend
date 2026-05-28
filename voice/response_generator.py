"""Response Generator — emotionally-aware LLM context assembly.

Translates CycleOutput into LLM prompt context. Does NOT generate content itself.
Passes raw LLM output to ResponseModulator for voice shaping.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from emotion.emotional_intelligence_core import CycleOutput
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class ResponseContext:
    """Context assembled for LLM from emotional runtime state."""
    session_id: str
    lineage_id: UUID
    emotional_summary: dict
    directive_summary: dict
    regulation_summary: dict
    rhythm_summary: dict
    max_sentences: int
    response_mode: str
    monotonic_timestamp: float


class LLMBackend(Protocol):
    """Protocol for pluggable LLM backends."""
    async def complete(self, system_prompt: str, user_context: str, max_sentences: int) -> str: ...


class DefaultLLMBackend:
    """Stub LLM — returns mode-appropriate placeholder text."""

    _RESPONSES = {
        "minimal": "I hear you.",
        "grounded": "Take your time. I'm here when you're ready.",
        "supportive": "That sounds challenging. You're handling it well.",
        "neutral": "I understand. How can I help?",
    }

    async def complete(self, system_prompt: str, user_context: str, max_sentences: int) -> str:
        mode = "neutral"
        for m in ("minimal", "grounded", "supportive"):
            if m in system_prompt.lower():
                mode = m
                break
        return self._RESPONSES.get(mode, self._RESPONSES["neutral"])


class ResponseGenerator:
    """Assembles emotional context for LLM and generates responses."""

    def __init__(self) -> None:
        self._prompt_cache: deque[str] = deque(maxlen=10)
        self._response_history: deque[str] = deque(maxlen=50)

    async def build_context(
        self, cycle_output: CycleOutput, lineage_id: UUID, timestamp: float
    ) -> ResponseContext:
        """Build ResponseContext from CycleOutput."""
        es = cycle_output.emotional_state
        d = cycle_output.directive
        reg = cycle_output.regulation
        rhy = cycle_output.rhythm_state

        # Derive response_mode
        response_mode = self._derive_mode(
            overload=reg.overload_detected,
            cognitive_load=es.cognitive_load,
            recovery_active=reg.recovery_mode_active,
            reassurance=d.reassurance_level,
            stress=es.stress,
        )

        return ResponseContext(
            session_id="",
            lineage_id=lineage_id,
            emotional_summary={
                "stress": es.stress,
                "engagement": es.engagement,
                "cognitive_load": es.cognitive_load,
                "recovery_state": es.recovery_state,
            },
            directive_summary={
                "verbosity_target": d.verbosity_target,
                "emotional_softness": d.emotional_softness,
                "reassurance_level": d.reassurance_level,
            },
            regulation_summary={
                "overload_detected": reg.overload_detected,
                "recovery_mode_active": reg.recovery_mode_active,
            },
            rhythm_summary={
                "conversational_pressure": rhy.conversational_pressure,
                "pause_comfort": rhy.pause_comfort,
            },
            max_sentences=d.max_response_sentences if hasattr(d, "max_response_sentences") else 3,
            response_mode=response_mode,
            monotonic_timestamp=timestamp,
        )

    async def generate(self, context: ResponseContext, llm_backend: LLMBackend | None = None) -> str:
        """Generate response text using LLM backend."""
        backend = llm_backend or DefaultLLMBackend()
        system_prompt = self._build_system_prompt(context)
        self._prompt_cache.append(system_prompt)

        user_context = f"User state: {context.response_mode} mode."

        try:
            response = await backend.complete(system_prompt, user_context, context.max_sentences)
        except Exception as e:
            logger.warning("llm_generation_failed", error=str(e))
            response = "I'm here. Take your time."

        self._response_history.append(response)
        return response

    def _derive_mode(
        self, overload: bool, cognitive_load: float,
        recovery_active: bool, reassurance: float, stress: float,
    ) -> str:
        if overload or cognitive_load > 0.7:
            return "minimal"
        if recovery_active:
            return "grounded"
        if reassurance > 0.6 and stress > 0.6:
            return "supportive"
        return "neutral"

    def _build_system_prompt(self, context: ResponseContext) -> str:
        mode = context.response_mode
        max_s = context.max_sentences

        prompts = {
            "minimal": (
                f"Respond in {mode} mode. Maximum {max_s} sentence(s). "
                "Be extremely brief. No questions. No elaboration. "
                "The user is cognitively overloaded."
            ),
            "grounded": (
                f"Respond in {mode} mode. Maximum {max_s} sentence(s). "
                "Be calm and grounding. Use simple language. "
                "The user is recovering. Do not rush them."
            ),
            "supportive": (
                f"Respond in {mode} mode. Maximum {max_s} sentence(s). "
                "Be warm and reassuring. Acknowledge difficulty. "
                "Do not minimize their experience."
            ),
            "neutral": (
                f"Respond in {mode} mode. Maximum {max_s} sentence(s). "
                "Be helpful and clear. Match the user's energy level."
            ),
        }
        return prompts.get(mode, prompts["neutral"])
