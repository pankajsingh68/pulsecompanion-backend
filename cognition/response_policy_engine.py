"""Response Policy Engine — decides WHAT type of response to produce, or silence.

The most important decision in the interaction loop. Runs before the LLM.
Integrates longitudinal RelationalPatternState as a modifier (not override).
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING

from emotion.emotional_intelligence_core import CycleOutput
from utils.logger import get_logger

if TYPE_CHECKING:
    from emotion.relational_pattern_memory import RelationalPatternState

logger = get_logger(__name__)

POLICY_VERSION = 2  # incremented: longitudinal integration added


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


@dataclass(frozen=True)
class ResponsePolicy:
    response_mode: str
    should_respond: bool
    silence_reason: str | None
    max_sentences: int
    max_questions: int
    emotional_tone: str
    allow_reflection: bool
    allow_encouragement: bool
    allow_practical_help: bool
    allow_proactive_checkin: bool
    pacing_density: str
    policy_version: int
    policy_confidence: float


# Mode severity for transition clamping
_MODE_ORDER = ["minimal", "grounding", "supportive", "neutral", "reflective", "practical"]


class ResponsePolicyEngine:
    """Decides response type or silence. Rate-clamps mode transitions.

    Accepts optional RelationalPatternState for longitudinal influence.
    Per-cycle state takes priority. Longitudinal history is a modifier.
    """

    def __init__(self) -> None:
        self._prev_mode: str = "neutral"
        self._mode_streak: int = 0
        self._pending_mode: str | None = None
        self._consecutive_system_turns: int = 0
        self._last_utterance_time: float = 0.0
        self._confidence_ema: float = 0.7
        self._history: deque[ResponsePolicy] = deque(maxlen=100)
        self._transition_log: deque[dict] = deque(maxlen=50)
        self._pattern_modifier_log: deque[dict] = deque(maxlen=50)
        self._silence_count: int = 0
        self._output: ResponsePolicy | None = None
        self._longitudinal_applied: bool = False
        self._active_modifiers: list[str] = []

    def evaluate(
        self,
        cycle_output: CycleOutput,
        silence_duration: float = 0.0,
        user_spoke_this_turn: bool = True,
        timestamp: float = 0.0,
        pattern_state: "RelationalPatternState | None" = None,
    ) -> ResponsePolicy:
        """Evaluate and produce ResponsePolicy from CycleOutput.

        Args:
            cycle_output: Current emotional intelligence cycle output.
            silence_duration: How long silence has lasted.
            user_spoke_this_turn: Whether user spoke this turn.
            timestamp: Monotonic timestamp.
            pattern_state: Optional longitudinal pattern state for modifiers.
        """
        es = cycle_output.emotional_state
        reg = cycle_output.regulation
        rhy = cycle_output.rhythm_state
        d = cycle_output.directive

        # Track consecutive system turns
        if not user_spoke_this_turn:
            self._consecutive_system_turns += 1
        else:
            self._consecutive_system_turns = 0

        # --- Silence decision ---
        should_respond = True
        silence_reason = None

        if reg.recovery_mode_active and es.stress < 0.5 and silence_duration < 4.0:
            should_respond = False
            silence_reason = "recovery_space"
        elif reg.overload_severity > 0.85 and (timestamp - self._last_utterance_time) < 8.0:
            should_respond = False
            silence_reason = "overload_protection"
        elif rhy.conversational_pressure > 0.8:
            should_respond = False
            silence_reason = "pressure_relief"
        elif self._consecutive_system_turns >= 3:
            should_respond = False
            silence_reason = "monologue_prevention"

        if not should_respond:
            self._silence_count += 1
            self._longitudinal_applied = False
            self._active_modifiers = []
            policy = ResponsePolicy(
                response_mode="silence", should_respond=False,
                silence_reason=silence_reason, max_sentences=0,
                max_questions=0, emotional_tone="neutral",
                allow_reflection=False, allow_encouragement=False,
                allow_practical_help=False, allow_proactive_checkin=False,
                pacing_density="sparse", policy_version=POLICY_VERSION,
                policy_confidence=self._confidence_ema,
            )
            self._output = policy
            self._history.append(policy)
            return policy

        # --- Mode derivation (per-cycle rules) ---
        mode = "neutral"
        max_sentences = 3
        max_questions = 1
        tone = "neutral"
        allow_reflection = False
        allow_encouragement = True
        allow_practical = True
        allow_proactive = d.allow_proactive_checkin
        pacing = "normal"

        stress = es.stress
        cog_load = es.cognitive_load
        engagement = es.engagement
        openness = es.emotional_openness
        reassurance = d.reassurance_level

        if reg.overload_detected or cog_load > 0.70:
            mode = "minimal"
            max_sentences = 1
            max_questions = 0
            pacing = "sparse"
            allow_practical = False
            tone = "minimal"
        elif reg.recovery_mode_active or stress > 0.75:
            mode = "grounding"
            max_sentences = 2
            max_questions = 0
            tone = "grounding"
            allow_encouragement = False
        elif 0.50 <= stress <= 0.75 and reassurance > 0.60:
            mode = "supportive"
            max_sentences = 2
            max_questions = 1
            tone = "warm"
        elif engagement > 0.60 and openness > 0.50 and stress < 0.40:
            mode = "reflective"
            max_sentences = 3
            max_questions = 1
            allow_reflection = True
        elif cog_load < 0.35 and engagement > 0.65:
            mode = "practical"
            max_sentences = 4
            max_questions = 1
            allow_practical = True

        # --- Longitudinal modifiers (applied AFTER per-cycle rules) ---
        self._longitudinal_applied = False
        self._active_modifiers = []

        if pattern_state is not None:
            self._longitudinal_applied = True
            modifiers: list[str] = []

            # Low trust → reduce questions, disable proactive
            if pattern_state.trust_stability < 0.3:
                max_questions = max(0, max_questions - 1)
                allow_proactive = False
                self._confidence_ema = max(0.0, self._confidence_ema - 0.15)
                modifiers.append("low_trust_reduction")

            # High overload frequency → bias toward minimal/grounding
            if pattern_state.overload_frequency > 0.6:
                # Lower thresholds by 0.10 — if stress > 0.65 (instead of 0.75)
                if stress > 0.65 and mode not in ("minimal", "grounding"):
                    mode = "grounding"
                    max_sentences = min(max_sentences, 2)
                    max_questions = 0
                    tone = "grounding"
                    modifiers.append("overload_frequency_bias")

            # Good recovery trend → allow one step warmer
            if pattern_state.recovery_trend > 0.5:
                mode_idx = _MODE_ORDER.index(mode) if mode in _MODE_ORDER else 3
                if mode_idx < len(_MODE_ORDER) - 1:
                    # Allow one step warmer (toward practical/reflective)
                    warmer_mode = _MODE_ORDER[min(mode_idx + 1, len(_MODE_ORDER) - 1)]
                    # Only apply if it's actually warmer (higher index)
                    if _MODE_ORDER.index(warmer_mode) > mode_idx:
                        mode = warmer_mode
                        modifiers.append("recovery_trend_warmth")

            # Chronically stressed → cap sentences, sparse pacing
            if pattern_state.stress_baseline > 0.65:
                max_sentences = min(max_sentences, 2)
                pacing = "sparse"
                modifiers.append("chronic_stress_cap")

            self._active_modifiers = modifiers
            if modifiers:
                self._pattern_modifier_log.append({
                    "modifiers": modifiers,
                    "trust": round(pattern_state.trust_stability, 3),
                    "overload_freq": round(pattern_state.overload_frequency, 3),
                    "recovery_trend": round(pattern_state.recovery_trend, 3),
                    "stress_baseline": round(pattern_state.stress_baseline, 3),
                })

        # --- Mode transition clamping ---
        mode = self._clamp_mode_transition(mode)

        # Update confidence EMA
        self._confidence_ema = 0.25 * es.confidence + 0.75 * self._confidence_ema

        if should_respond:
            self._last_utterance_time = timestamp

        policy = ResponsePolicy(
            response_mode=mode, should_respond=True,
            silence_reason=None, max_sentences=max_sentences,
            max_questions=max_questions, emotional_tone=tone,
            allow_reflection=allow_reflection,
            allow_encouragement=allow_encouragement,
            allow_practical_help=allow_practical,
            allow_proactive_checkin=allow_proactive,
            pacing_density=pacing, policy_version=POLICY_VERSION,
            policy_confidence=round(_clamp(self._confidence_ema), 4),
        )
        self._output = policy
        self._history.append(policy)
        return policy

    def _clamp_mode_transition(self, proposed: str) -> str:
        """Prevent large mode jumps. Require 3 stable cycles for distant transitions."""
        if proposed == self._prev_mode:
            self._mode_streak += 1
            self._pending_mode = None
            return proposed

        # Check distance
        prev_idx = _MODE_ORDER.index(self._prev_mode) if self._prev_mode in _MODE_ORDER else 3
        prop_idx = _MODE_ORDER.index(proposed) if proposed in _MODE_ORDER else 3

        if abs(prop_idx - prev_idx) <= 1:
            # Adjacent — allow immediately
            self._transition_log.append({"from": self._prev_mode, "to": proposed})
            self._prev_mode = proposed
            self._mode_streak = 1
            self._pending_mode = None
            return proposed

        # Distant — require 3 stable cycles
        if self._pending_mode == proposed:
            self._mode_streak += 1
            if self._mode_streak >= 3:
                self._transition_log.append({"from": self._prev_mode, "to": proposed})
                self._prev_mode = proposed
                self._pending_mode = None
                return proposed
        else:
            self._pending_mode = proposed
            self._mode_streak = 1

        return self._prev_mode  # hold current mode

    async def get_current_policy(self) -> ResponsePolicy | None:
        return self._output

    async def get_policy_diagnostics(self) -> dict:
        return {
            "mode_history": [p.response_mode for p in list(self._history)[-10:]],
            "silence_count": self._silence_count,
            "transition_log": list(self._transition_log)[-10:],
            "confidence_trend": round(self._confidence_ema, 4),
            "longitudinal_influence_applied": self._longitudinal_applied,
            "pattern_modifiers_active": list(self._active_modifiers),
            "pattern_modifier_log": list(self._pattern_modifier_log)[-10:],
        }
