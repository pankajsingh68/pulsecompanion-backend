"""Conversational Rhythm Engine — models human conversational pacing.

Makes interaction feel human by understanding when to slow down,
when silence is comfort, and when pressure is building.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from utils.logger import get_logger

logger = get_logger(__name__)

RHYTHM_VERSION = 1


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


@dataclass(frozen=True)
class RhythmSignal:
    """Input signal for rhythm analysis."""
    pause_duration: float
    interruption_frequency: float
    speech_pacing: float
    silence_comfort: float
    response_latency: float
    conversational_volatility: float
    timestamp: float


@dataclass(frozen=True)
class RhythmState:
    """Output: current conversational rhythm state."""
    conversational_pressure: float
    pause_comfort: float
    interruption_load: float
    pacing_stability: float
    urgency_level: float
    silence_tolerance: float
    rhythm_version: int


EMA_ALPHA = 0.25
MAX_DELTA = 0.15


class ConversationalRhythmEngine:
    """Models conversational pacing and regulation state."""

    def __init__(self) -> None:
        self._prev: dict[str, float] = {
            "conversational_pressure": 0.3,
            "pause_comfort": 0.5,
            "interruption_load": 0.2,
            "pacing_stability": 0.7,
            "urgency_level": 0.3,
            "silence_tolerance": 0.5,
        }
        self._prev_smoothed: dict[str, float] = dict(self._prev)
        self._output: RhythmState | None = None
        self._signal_history: deque[RhythmSignal] = deque(maxlen=200)
        self._volatility_samples: deque[float] = deque(maxlen=100)
        self._diagnostics: deque[dict] = deque(maxlen=100)
        self._conflict_count: int = 0

    def process_cycle(self, signal: RhythmSignal) -> RhythmState:
        """Process one rhythm cycle. Never raises."""
        self._signal_history.append(signal)
        self._volatility_samples.append(signal.conversational_volatility)

        raw = dict(self._prev)

        # Interruption → raise pressure
        if signal.interruption_frequency > 0.3:
            raw["conversational_pressure"] = _clamp(
                raw["conversational_pressure"] + 0.1 * signal.interruption_frequency
            )
            raw["interruption_load"] = _clamp(
                raw["interruption_load"] + 0.1 * signal.interruption_frequency
            )

        # Long pauses + low interruption → raise pause_comfort
        if signal.pause_duration > 0.5 and signal.interruption_frequency < 0.2:
            raw["pause_comfort"] = _clamp(raw["pause_comfort"] + 0.05)

        # Rapid pacing changes → reduce stability
        pacing_delta = abs(signal.speech_pacing - 0.5)
        if pacing_delta > 0.3:
            raw["pacing_stability"] = _clamp(raw["pacing_stability"] - pacing_delta * 0.3)

        # High volatility → increase urgency
        if signal.conversational_volatility > 0.5:
            raw["urgency_level"] = _clamp(
                raw["urgency_level"] + 0.08 * signal.conversational_volatility
            )

        # Silence after calm → raise silence_tolerance
        if signal.silence_comfort > 0.5 and raw["conversational_pressure"] < 0.4:
            raw["silence_tolerance"] = _clamp(raw["silence_tolerance"] + 0.04)

        # Contradiction: high pause_comfort AND high interruption_load
        if raw["pause_comfort"] > 0.6 and raw["interruption_load"] > 0.6:
            raw["pause_comfort"] = 0.5 * raw["pause_comfort"] + 0.5 * 0.5
            raw["interruption_load"] = 0.5 * raw["interruption_load"] + 0.5 * 0.5
            raw["pacing_stability"] = _clamp(raw["pacing_stability"] - 0.1)
            self._conflict_count += 1

        # EMA smoothing
        smoothed: dict[str, float] = {}
        for dim in self._prev:
            smoothed[dim] = EMA_ALPHA * raw[dim] + (1 - EMA_ALPHA) * self._prev_smoothed[dim]

        # Rate clamping
        final: dict[str, float] = {}
        for dim in self._prev:
            lo = self._prev[dim] - MAX_DELTA
            hi = self._prev[dim] + MAX_DELTA
            final[dim] = _clamp(smoothed[dim], lo, hi)
            final[dim] = _clamp(final[dim])

        self._prev = dict(final)
        self._prev_smoothed = dict(smoothed)

        self._output = RhythmState(
            conversational_pressure=round(final["conversational_pressure"], 6),
            pause_comfort=round(final["pause_comfort"], 6),
            interruption_load=round(final["interruption_load"], 6),
            pacing_stability=round(final["pacing_stability"], 6),
            urgency_level=round(final["urgency_level"], 6),
            silence_tolerance=round(final["silence_tolerance"], 6),
            rhythm_version=RHYTHM_VERSION,
        )

        self._diagnostics.append({"conflicts": self._conflict_count})
        return self._output

    async def get_current_rhythm(self) -> RhythmState | None:
        return self._output

    async def get_rhythm_health(self) -> dict:
        return {
            "signal_count": len(self._signal_history),
            "conflict_count": self._conflict_count,
            "smoothing_rate": EMA_ALPHA,
        }
