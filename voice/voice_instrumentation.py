"""Voice instrumentation — per-stage latency tracing via AsyncEventBus.

Lightweight async context manager that records stage timing and emits events.
"""

from __future__ import annotations

import time
from collections import deque
from contextlib import asynccontextmanager
from dataclasses import dataclass
from uuid import UUID

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class VoiceStageEvent:
    """Per-stage latency event emitted on the bus."""
    event_type: str
    session_id: str
    lineage_id: UUID
    stage_latency_ms: float
    success: bool
    degraded: bool
    monotonic_timestamp: float


class VoiceInstrumentation:
    """Tracks per-stage latency for the voice pipeline."""

    def __init__(self, bus=None) -> None:
        self._bus = bus
        self._latencies: dict[str, deque] = {}

    @asynccontextmanager
    async def stage_timer(
        self, stage_name: str, lineage_id: UUID, session_id: str, degraded: bool = False
    ):
        """Async context manager that times a stage and emits event.

        Usage:
            async with instrumentation.stage_timer("voice.stage.prosody", lid, sid):
                result = prosody.extract(...)
        """
        start = time.monotonic()
        success = True
        try:
            yield
        except Exception:
            success = False
            raise
        finally:
            elapsed_ms = (time.monotonic() - start) * 1000

            # Track latency
            if stage_name not in self._latencies:
                self._latencies[stage_name] = deque(maxlen=200)
            self._latencies[stage_name].append(elapsed_ms)

            # Emit event
            event = VoiceStageEvent(
                event_type=stage_name,
                session_id=session_id,
                lineage_id=lineage_id,
                stage_latency_ms=round(elapsed_ms, 3),
                success=success,
                degraded=degraded,
                monotonic_timestamp=time.monotonic(),
            )

            if self._bus:
                try:
                    await self._bus.emit(stage_name, event)
                except Exception:
                    pass

    def get_stage_latencies(self) -> dict[str, dict]:
        """Get latency stats per stage."""
        result = {}
        for stage, latencies in self._latencies.items():
            if latencies:
                sorted_l = sorted(latencies)
                n = len(sorted_l)
                result[stage] = {
                    "mean_ms": round(sum(sorted_l) / n, 3),
                    "p95_ms": round(sorted_l[int(n * 0.95)] if n > 1 else sorted_l[0], 3),
                    "samples": n,
                }
        return result
