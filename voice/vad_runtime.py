"""VAD Runtime — Voice Activity Detection using configurable backend.

Consumes raw audio chunks, emits speech_start/speech_end/silence events.
Runs detection in thread pool to never block async loop.
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass
from typing import AsyncIterator, Protocol
from uuid import UUID, uuid4

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class VADEvent:
    """Voice activity detection event."""
    event_type: str
    session_id: str
    lineage_id: UUID
    monotonic_timestamp: float
    silence_duration: float
    confidence: float


class VADBackend(Protocol):
    """Protocol for pluggable VAD backends (Silero, WebRTC, etc.)."""
    def detect(self, audio_chunk: bytes) -> tuple[bool, float]: ...


class DefaultVADBackend:
    """Simple energy-based VAD fallback when no ML model available."""

    def __init__(self, energy_threshold: float = 0.01) -> None:
        self._threshold = energy_threshold

    def detect(self, audio_chunk: bytes) -> tuple[bool, float]:
        if not audio_chunk:
            return False, 0.0
        energy = sum(abs(b - 128) for b in audio_chunk) / max(len(audio_chunk), 1) / 128.0
        is_speech = energy > self._threshold
        confidence = min(1.0, energy * 5.0) if is_speech else 1.0 - min(1.0, energy * 10.0)
        return is_speech, confidence


class VADRuntime:
    """Real-time voice activity detection runtime.

    Mints lineage_id at speech_start — carried through full segment.
    Emits events onto AsyncEventBus. Never blocks async loop.
    """

    def __init__(
        self,
        session_id: str,
        backend: VADBackend | None = None,
        silence_threshold_s: float = 1.5,
        bus=None,
    ) -> None:
        self._session_id = session_id
        self._backend = backend or DefaultVADBackend()
        self._silence_threshold = silence_threshold_s
        self._bus = bus
        self._is_speaking = False
        self._current_lineage: UUID | None = None
        self._silence_start: float = 0.0
        self._last_speech_time: float = 0.0
        self._events: deque[VADEvent] = deque(maxlen=200)
        self._degraded = False

    @property
    def current_lineage_id(self) -> UUID | None:
        return self._current_lineage

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    async def process_chunk(self, audio_chunk: bytes, timestamp: float) -> VADEvent | None:
        """Process one audio chunk. Returns VADEvent if state changed."""
        try:
            loop = asyncio.get_running_loop()
            is_speech, confidence = await loop.run_in_executor(
                None, self._backend.detect, audio_chunk
            )
        except Exception as e:
            logger.warning("vad_detection_failed", error=str(e))
            self._degraded = True
            event = VADEvent(
                event_type="vad.degraded",
                session_id=self._session_id,
                lineage_id=self._current_lineage or uuid4(),
                monotonic_timestamp=timestamp,
                silence_duration=0.0,
                confidence=0.0,
            )
            self._events.append(event)
            await self._emit(event)
            return event

        event = None

        if is_speech and not self._is_speaking:
            # Speech start — mint lineage
            self._is_speaking = True
            self._current_lineage = uuid4()
            self._last_speech_time = timestamp
            event = VADEvent(
                event_type="vad.speech_start",
                session_id=self._session_id,
                lineage_id=self._current_lineage,
                monotonic_timestamp=timestamp,
                silence_duration=0.0,
                confidence=confidence,
            )

        elif not is_speech and self._is_speaking:
            # Speech end
            self._is_speaking = False
            self._silence_start = timestamp
            event = VADEvent(
                event_type="vad.speech_end",
                session_id=self._session_id,
                lineage_id=self._current_lineage or uuid4(),
                monotonic_timestamp=timestamp,
                silence_duration=0.0,
                confidence=confidence,
            )

        elif not is_speech and not self._is_speaking:
            # Check silence duration
            silence_dur = timestamp - self._silence_start if self._silence_start > 0 else 0.0
            if silence_dur >= self._silence_threshold:
                event = VADEvent(
                    event_type="vad.silence_detected",
                    session_id=self._session_id,
                    lineage_id=self._current_lineage or uuid4(),
                    monotonic_timestamp=timestamp,
                    silence_duration=silence_dur,
                    confidence=confidence,
                )
                self._silence_start = timestamp  # reset

        if is_speech:
            self._last_speech_time = timestamp

        if event:
            self._events.append(event)
            await self._emit(event)

        return event

    async def _emit(self, event: VADEvent) -> None:
        if self._bus:
            try:
                await self._bus.emit(event.event_type, event)
            except Exception:
                pass
