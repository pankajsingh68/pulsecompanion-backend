"""Streaming transcription — consumes audio, emits partial + final text.

Model injected via TranscriptionBackend protocol. lineage_id forwarded from VAD.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class TranscriptionEvent:
    event_type: str
    session_id: str
    lineage_id: UUID
    text: str
    is_final: bool
    monotonic_timestamp: float
    processing_latency: float


class TranscriptionBackend(Protocol):
    """Protocol for pluggable STT backends."""
    async def transcribe_chunk(self, audio: bytes) -> tuple[str, bool]: ...
    async def finalize(self) -> str: ...


class DefaultTranscriptionBackend:
    """Stub backend — returns empty text. Replace with Whisper/SenseVoice."""

    async def transcribe_chunk(self, audio: bytes) -> tuple[str, bool]:
        return "", False

    async def finalize(self) -> str:
        return ""


class TranscriptionStream:
    """Streaming speech-to-text with partial emissions."""

    def __init__(
        self, session_id: str, backend: TranscriptionBackend | None = None, bus=None
    ) -> None:
        self._session_id = session_id
        self._backend = backend or DefaultTranscriptionBackend()
        self._bus = bus
        self._events: deque[TranscriptionEvent] = deque(maxlen=200)
        self._accumulated_text: str = ""

    async def process_audio(
        self, audio_chunk: bytes, lineage_id: UUID, timestamp: float
    ) -> TranscriptionEvent | None:
        """Process audio chunk, emit transcription event if text available."""
        start = timestamp
        try:
            text, is_final = await self._backend.transcribe_chunk(audio_chunk)
        except Exception as e:
            logger.warning("transcription_failed", error=str(e))
            event = TranscriptionEvent(
                event_type="transcription.degraded",
                session_id=self._session_id,
                lineage_id=lineage_id,
                text="",
                is_final=False,
                monotonic_timestamp=timestamp,
                processing_latency=0.0,
            )
            self._events.append(event)
            if self._bus:
                try:
                    await self._bus.emit("transcription.degraded", event)
                except Exception:
                    pass
            return event

        if not text:
            return None

        self._accumulated_text += " " + text if self._accumulated_text else text
        event_type = "transcription.final" if is_final else "transcription.partial"

        event = TranscriptionEvent(
            event_type=event_type,
            session_id=self._session_id,
            lineage_id=lineage_id,
            text=self._accumulated_text.strip() if is_final else text,
            is_final=is_final,
            monotonic_timestamp=timestamp,
            processing_latency=0.0,
        )

        if is_final:
            self._accumulated_text = ""

        self._events.append(event)
        if self._bus:
            try:
                await self._bus.emit(event_type, event)
            except Exception:
                pass
        return event

    async def finalize_segment(self, lineage_id: UUID, timestamp: float) -> TranscriptionEvent:
        """Force finalize current segment."""
        try:
            final_text = await self._backend.finalize()
        except Exception:
            final_text = self._accumulated_text

        text = final_text or self._accumulated_text
        self._accumulated_text = ""

        event = TranscriptionEvent(
            event_type="transcription.final",
            session_id=self._session_id,
            lineage_id=lineage_id,
            text=text.strip(),
            is_final=True,
            monotonic_timestamp=timestamp,
            processing_latency=0.0,
        )
        self._events.append(event)
        return event
