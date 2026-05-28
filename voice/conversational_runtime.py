"""Conversational Runtime — turn-taking, interruption, silence management.

Makes the system feel human. Coordinates timing decisions.
Silence is not a gap to fill.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from emotion.conversational_rhythm_engine import RhythmState
from emotion.overload_regulation_controller import RegulationDecision
from utils.logger import get_logger

logger = get_logger(__name__)

TURN_VERSION = 1


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


@dataclass(frozen=True)
class TurnState:
    current_speaker: str
    turn_duration: float
    silence_duration: float
    interruption_count: int
    waiting_for_user: bool
    system_should_yield: bool
    silence_is_healthy: bool
    turn_version: int


class ConversationalRuntime:
    """Manages turn-taking loop with adaptive timing.

    silence_is_healthy must be checked before every response initiation.
    If True, the system waits. It does not speak.
    """

    def __init__(self, session_id: str) -> None:
        self._session_id = session_id
        self._current_speaker: str = "silence"
        self._turn_start: float = 0.0
        self._silence_start: float = 0.0
        self._interruption_count: int = 0
        self._consecutive_interruptions: int = 0
        self._pressure_cycles_remaining: int = 0
        self._max_sentences_override: int | None = None
        self._history: deque[TurnState] = deque(maxlen=100)
        self._output: TurnState | None = None

    def user_started_speaking(self, timestamp: float) -> TurnState:
        """User began speaking — system should yield if outputting."""
        if self._current_speaker == "system":
            self._interruption_count += 1
            self._consecutive_interruptions += 1
            if self._consecutive_interruptions >= 3:
                self._pressure_cycles_remaining = 5
                self._max_sentences_override = 1
                logger.info("pressure_escalation", session_id=self._session_id)

        self._current_speaker = "user"
        self._turn_start = timestamp
        return self._build_state(timestamp)

    def user_stopped_speaking(self, timestamp: float) -> TurnState:
        """User stopped — transition to silence."""
        self._current_speaker = "silence"
        self._silence_start = timestamp
        return self._build_state(timestamp)

    def system_starts_speaking(self, timestamp: float) -> TurnState:
        """System begins response."""
        self._current_speaker = "system"
        self._turn_start = timestamp
        # Do NOT reset consecutive_interruptions here — only reset when
        # a full turn completes without interruption
        if self._pressure_cycles_remaining > 0:
            self._pressure_cycles_remaining -= 1
            if self._pressure_cycles_remaining <= 0:
                self._max_sentences_override = None
        return self._build_state(timestamp)

    def compute_response_delay(
        self,
        rhythm: RhythmState,
        regulation: RegulationDecision,
        cognitive_load: float,
        timestamp: float,
    ) -> float:
        """Compute how long to wait before responding.

        Adaptive: cognitive_load > 0.7 → wait cognitive_load * 2.0s
        Pause comfort: extend by pause_comfort * 1.5s
        """
        base_delay = 0.5

        # Adaptive waiting for cognitive load
        if cognitive_load > 0.7:
            base_delay = cognitive_load * 2.0

        # Pause comfort extension
        if rhythm.pause_comfort > 0.6:
            base_delay += rhythm.pause_comfort * 1.5

        return min(base_delay, 5.0)

    def should_speak(
        self,
        regulation: RegulationDecision,
        silence_duration: float,
        speech_instability: float = 0.0,
    ) -> bool:
        """Check if system should initiate speech.

        silence_is_healthy must be checked before every response.
        """
        # Recovery mode + short silence → silence is healthy, do not speak
        if regulation.recovery_mode_active and silence_duration < 4.0:
            return False

        # Overload + instability → yield
        if regulation.overload_detected and speech_instability > 0.6:
            return False

        return True

    def get_max_sentences(self) -> int:
        """Get current max sentences (may be overridden by pressure)."""
        return self._max_sentences_override or 4

    @property
    def current_state(self) -> TurnState | None:
        return self._output

    def _build_state(self, timestamp: float) -> TurnState:
        silence_dur = (
            timestamp - self._silence_start
            if self._current_speaker == "silence" and self._silence_start > 0
            else 0.0
        )
        turn_dur = timestamp - self._turn_start if self._turn_start > 0 else 0.0

        # Silence is healthy check
        silence_healthy = (
            self._current_speaker == "silence"
            and silence_dur < 4.0
            and silence_dur > 0.5
        )

        self._output = TurnState(
            current_speaker=self._current_speaker,
            turn_duration=round(turn_dur, 3),
            silence_duration=round(silence_dur, 3),
            interruption_count=self._interruption_count,
            waiting_for_user=self._current_speaker == "silence",
            system_should_yield=self._current_speaker == "system" and self._consecutive_interruptions > 0,
            silence_is_healthy=silence_healthy,
            turn_version=TURN_VERSION,
        )
        self._history.append(self._output)
        return self._output
