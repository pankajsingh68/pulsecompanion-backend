"""Prosody Extractor — behavioral signal extraction from audio.

Extracts pacing_pressure, hesitation_index, speech_instability,
urgency_level, silence_comfort, strain_index. Never infers emotion labels.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from uuid import UUID

from utils.logger import get_logger

logger = get_logger(__name__)


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


@dataclass(frozen=True)
class ProsodySignal:
    lineage_id: UUID
    session_id: str
    pacing_pressure: float
    hesitation_index: float
    speech_instability: float
    urgency_level: float
    silence_comfort: float
    strain_index: float
    extraction_confidence: float
    monotonic_timestamp: float


class ProsodyExtractor:
    """Extracts behavioral prosody signals from audio features.

    Baseline is session-scoped. All values bounded [0,1].
    """

    def __init__(self, session_id: str) -> None:
        self._session_id = session_id
        self._energy_baseline: float = 0.0
        self._rate_baseline: float = 0.5
        self._sample_count: int = 0
        self._history: deque[ProsodySignal] = deque(maxlen=200)
        self._silence_durations: deque[float] = deque(maxlen=50)

    def extract(
        self,
        audio_chunk: bytes,
        lineage_id: UUID,
        timestamp: float,
        silence_duration: float = 0.0,
    ) -> ProsodySignal:
        """Extract prosody signals from audio chunk.

        If audio quality too low: extraction_confidence < 0.3.
        """
        self._sample_count += 1
        if silence_duration > 0:
            self._silence_durations.append(silence_duration)

        # Compute energy from audio bytes
        if not audio_chunk or len(audio_chunk) < 10:
            signal = ProsodySignal(
                lineage_id=lineage_id, session_id=self._session_id,
                pacing_pressure=0.3, hesitation_index=0.3,
                speech_instability=0.2, urgency_level=0.2,
                silence_comfort=0.5, strain_index=0.2,
                extraction_confidence=0.1, monotonic_timestamp=timestamp,
            )
            self._history.append(signal)
            return signal

        # Energy analysis
        energy = sum(abs(b - 128) for b in audio_chunk) / len(audio_chunk) / 128.0
        energy = _clamp(energy)

        # Update baseline (EMA)
        if self._energy_baseline == 0:
            self._energy_baseline = energy
        else:
            self._energy_baseline = 0.1 * energy + 0.9 * self._energy_baseline

        # Pacing pressure: deviation from baseline energy
        energy_deviation = abs(energy - self._energy_baseline)
        pacing_pressure = _clamp(energy_deviation * 3.0)

        # Hesitation: low energy variance within chunk (pauses within speech)
        chunk_variance = self._compute_variance(audio_chunk)
        hesitation_index = _clamp(1.0 - chunk_variance * 5.0)

        # Speech instability: high variance = unstable
        speech_instability = _clamp(chunk_variance * 4.0)

        # Urgency: high energy + high rate
        urgency_level = _clamp(energy * 1.5 + pacing_pressure * 0.5)

        # Silence comfort: stable silence pattern
        silence_comfort = 0.5
        if self._silence_durations:
            avg_silence = sum(self._silence_durations) / len(self._silence_durations)
            silence_comfort = _clamp(avg_silence / 3.0)

        # Strain: energy above baseline
        strain_index = _clamp((energy - self._energy_baseline) * 2.0)

        # Confidence based on sample count and energy level
        confidence = _clamp(min(self._sample_count / 10.0, 1.0) * (0.5 + energy))

        signal = ProsodySignal(
            lineage_id=lineage_id,
            session_id=self._session_id,
            pacing_pressure=round(pacing_pressure, 6),
            hesitation_index=round(hesitation_index, 6),
            speech_instability=round(speech_instability, 6),
            urgency_level=round(urgency_level, 6),
            silence_comfort=round(silence_comfort, 6),
            strain_index=round(strain_index, 6),
            extraction_confidence=round(confidence, 6),
            monotonic_timestamp=timestamp,
        )
        self._history.append(signal)
        return signal

    def _compute_variance(self, audio: bytes) -> float:
        if len(audio) < 4:
            return 0.0
        values = [abs(b - 128) / 128.0 for b in audio[:100]]
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        return min(1.0, variance)
