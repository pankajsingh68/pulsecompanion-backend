"""Response Constraint Enforcer — enforces runtime constraints on LLM output.

The LLM may ignore instructions. This module does not.
"""

from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass

from cognition.response_policy_engine import ResponsePolicy
from utils.logger import get_logger

logger = get_logger(__name__)

ENFORCEMENT_VERSION = 1

FALLBACKS = {
    "minimal": "I hear you.",
    "grounding": "Take your time.",
    "supportive": "I'm with you.",
    "reflective": "Tell me more.",
    "practical": "Let's think through this.",
    "neutral": "Go on.",
}

# Overreach patterns — removed in "minimal" and "grounding" modes
OVERREACH_PATTERNS = [
    "i understand how you feel",
    "that must be really hard",
    "you should",
    "you need to",
    "everything will be okay",
    "i'm here for you",
]


@dataclass(frozen=True)
class EnforcedResponse:
    original_text: str
    enforced_text: str
    sentences_removed: int
    questions_removed: int
    was_truncated: bool
    enforcement_version: int


class ResponseConstraintEnforcer:
    """Enforces runtime constraints on LLM output post-generation."""

    def __init__(self, bus=None) -> None:
        self._bus = bus
        self._history: deque[EnforcedResponse] = deque(maxlen=100)
        self._violation_log: deque[dict] = deque(maxlen=50)
        self._truncation_count: int = 0
        self._question_removal_count: int = 0
        self._overreach_removal_count: int = 0
        self._fallback_count: int = 0

    def enforce(self, text: str, policy: ResponsePolicy) -> EnforcedResponse:
        """Enforce all constraints on LLM output. Returns EnforcedResponse."""
        original = text
        sentences_removed = 0
        questions_removed = 0
        was_truncated = False

        # Step 1: Sentence splitting
        sentences = self._split_sentences(text)

        # Step 2: Question removal
        if policy.max_questions == 0:
            before = len(sentences)
            sentences = [s for s in sentences if not s.strip().endswith("?")]
            questions_removed = before - len(sentences)
            self._question_removal_count += questions_removed
        elif policy.max_questions == 1:
            question_indices = [i for i, s in enumerate(sentences) if s.strip().endswith("?")]
            if len(question_indices) > 1:
                # Keep only the last question
                to_remove = question_indices[:-1]
                sentences = [s for i, s in enumerate(sentences) if i not in to_remove]
                questions_removed = len(to_remove)
                self._question_removal_count += questions_removed

        # Step 3: Sentence count enforcement
        if len(sentences) > policy.max_sentences:
            was_truncated = True
            sentences_removed += len(sentences) - policy.max_sentences
            sentences = sentences[:policy.max_sentences]
            self._truncation_count += 1

        # Step 4: Emotional overreach detection
        if policy.response_mode in ("minimal", "grounding"):
            filtered = []
            for s in sentences:
                s_lower = s.lower()
                if any(pattern in s_lower for pattern in OVERREACH_PATTERNS):
                    sentences_removed += 1
                    self._overreach_removal_count += 1
                    self._violation_log.append({
                        "type": "overreach", "sentence": s[:80],
                        "mode": policy.response_mode,
                    })
                    # Emit overreach event
                    self._emit_overreach(policy.response_mode, s)
                else:
                    filtered.append(s)
            sentences = filtered

        # Step 5: Empty response guard
        enforced_text = " ".join(sentences).strip()
        if not enforced_text:
            enforced_text = FALLBACKS.get(policy.response_mode, FALLBACKS["neutral"])
            self._fallback_count += 1

        result = EnforcedResponse(
            original_text=original,
            enforced_text=enforced_text,
            sentences_removed=sentences_removed,
            questions_removed=questions_removed,
            was_truncated=was_truncated,
            enforcement_version=ENFORCEMENT_VERSION,
        )
        self._history.append(result)
        return result

    def _split_sentences(self, text: str) -> list[str]:
        """Split on sentence boundaries. Preserve endings."""
        parts = re.split(r'(?<=[.!?])\s+', text.strip())
        return [p for p in parts if p.strip()]

    def _emit_overreach(self, mode: str, sentence: str) -> None:
        """Emit overreach detection event (fire-and-forget)."""
        if self._bus:
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._bus.emit("cognition.overreach_detected", {
                        "mode": mode, "sentence": sentence[:80],
                    }))
            except Exception:
                pass
        logger.info("overreach_detected", mode=mode, sentence=sentence[:50])

    async def get_enforcement_diagnostics(self) -> dict:
        return {
            "truncation_count": self._truncation_count,
            "question_removal_count": self._question_removal_count,
            "overreach_removal_count": self._overreach_removal_count,
            "fallback_count": self._fallback_count,
            "violation_log": list(self._violation_log)[-10:],
        }
