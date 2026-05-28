"""Voice Output Stream — streaming TTS with modulation parameters.

Streams chunks as ready. Handles interruption gracefully.
TTS backend injected via protocol.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import AsyncIterator, Protocol
from uuid import UUID

from voice.response_modulator import VoiceModulation
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class VoiceOutputEvent:
    event_type: str
    lineage_id: UUID
    session_id: str
    chunk_index: int
    is_final: bool
    modulation_applied: VoiceModulation
    monotonic_timestamp: float


class TTSBackend(Protocol):
    """Protocol for pluggable TTS backends."""
    async def synthesize_chunk(self, text: str, rate: float, softness: float) -> bytes: ...


class DefaultTTSBackend:
    """Stub TTS — returns empty bytes. Replace with real TTS."""

    async def synthesize_chunk(self, text: str, rate: float, softness: float) -> bytes:
        return b""


class VoiceOutputStream:
    """Streaming TTS output with modulation and interruption support."""

    def __init__(
        self, session_id: str, backend: TTSBackend | None = None, bus=None
    ) -> None:
        self._session_id = session_id
        self._backend = backend or DefaultTTSBackend()
        self._bus = bus
        self._events: deque[VoiceOutputEvent] = deque(maxlen=200)
        self._interrupted = False
        self._chunk_counter = 0

    async def stream_response(
        self,
        text: str,
        modulation: VoiceModulation,
        lineage_id: UUID,
        timestamp: float,
    ) -> AsyncIterator[VoiceOutputEvent]:
        """Stream TTS output chunks. Yields VoiceOutputEvents."""
        self._interrupted = False
        sentences = [s.strip() for s in text.split(".") if s.strip()]
        sentences = sentences[:modulation.max_response_sentences]

        for i, sentence in enumerate(sentences):
            if self._interrupted:
                event = VoiceOutputEvent(
                    event_type="voice.interrupted",
                    lineage_id=lineage_id,
                    session_id=self._session_id,
                    chunk_index=self._chunk_counter,
                    is_final=True,
                    modulation_applied=modulation,
                    monotonic_timestamp=timestamp,
                )
                self._events.append(event)
                yield event
                return

            self._chunk_counter += 1
            is_final = (i == len(sentences) - 1)

            try:
                await self._backend.synthesize_chunk(
                    sentence, modulation.speaking_rate, modulation.softness_level
                )
            except Exception as e:
                logger.warning("tts_synthesis_failed", error=str(e))

            event = VoiceOutputEvent(
                event_type="voice.chunk_ready" if not is_final else "voice.complete",
                lineage_id=lineage_id,
                session_id=self._session_id,
                chunk_index=self._chunk_counter,
                is_final=is_final,
                modulation_applied=modulation,
                monotonic_timestamp=timestamp,
            )
            self._events.append(event)
            yield event

    def interrupt(self) -> None:
        """Signal interruption — stops output gracefully."""
        self._interrupted = True
        logger.info("voice_output_interrupted", session_id=self._session_id)
