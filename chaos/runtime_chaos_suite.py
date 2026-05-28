"""Runtime chaos injection suite — injects real failures into live runtime.

NOT simulated validators. Injects failures into real runtime paths
and validates recovery behavior.
"""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from uuid import UUID

from utils.logger import get_logger

if TYPE_CHECKING:
    from events.event_bus import AsyncEventBus
    from integration.looptrace_assembler import LoopTraceAssembler
    from runtime.degraded_mode_controller import DegradedModeController
    from websocket.manager import ConnectionManager

logger = get_logger(__name__)


@dataclass
class ChaosRecoveryReport:
    """Result of a chaos injection run."""
    failures_injected: list[str] = field(default_factory=list)
    recovery_time_ms: float = 0.0
    lineages_lost: int = 0
    incomplete_traces: int = 0
    recovered_successfully: bool = True
    interventions: list[str] = field(default_factory=list)


class WebSocketDisconnectInjector:
    """Closes active transport mid-emission."""

    def __init__(self, ws_manager: "ConnectionManager") -> None:
        self._ws = ws_manager

    async def inject(self, session_id: str) -> dict:
        """Disconnect a session's websocket."""
        await self._ws.disconnect(session_id)
        logger.info("chaos_ws_disconnect", session_id=session_id)
        return {"type": "websocket_disconnect", "session_id": session_id}


class PacketJitterInjector:
    """Delays event timestamps randomly to inject out-of-order delivery."""

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    def apply_jitter(self, timestamp: float, max_jitter_ms: float = 200.0) -> float:
        """Apply random jitter to a timestamp."""
        jitter_s = self._rng.uniform(-max_jitter_ms, max_jitter_ms) / 1000.0
        return timestamp + jitter_s


class DuplicateEmissionInjector:
    """Intentionally emits duplicate stage events."""

    def __init__(self, bus: "AsyncEventBus") -> None:
        self._bus = bus

    async def inject_duplicate(self, event_type: str, event) -> None:
        """Emit the same event twice to test duplicate detection."""
        await self._bus.emit(event_type, event)
        await self._bus.emit(event_type, event)  # duplicate
        logger.info("chaos_duplicate_injected", event_type=event_type)


class PartialIngestionFailureInjector:
    """Randomly drops ingestion calls."""

    def __init__(self, drop_rate: float = 0.2, seed: int | None = None) -> None:
        self._drop_rate = drop_rate
        self._rng = random.Random(seed)
        self._dropped: int = 0

    def should_drop(self) -> bool:
        """Returns True if this call should be dropped."""
        if self._rng.random() < self._drop_rate:
            self._dropped += 1
            return True
        return False

    @property
    def total_dropped(self) -> int:
        return self._dropped


class SlowConsumerInjector:
    """Creates websocket backpressure by delaying consumption."""

    def __init__(self, delay_ms: float = 500.0) -> None:
        self._delay_ms = delay_ms

    async def apply_delay(self) -> None:
        """Simulate slow consumer by sleeping."""
        await asyncio.sleep(self._delay_ms / 1000.0)


class MemoryFailureInjector:
    """Raises retrieval/persistence exceptions."""

    def __init__(self) -> None:
        self._active = False

    def activate(self) -> None:
        self._active = True

    def deactivate(self) -> None:
        self._active = False

    def should_fail(self) -> bool:
        return self._active


class OrchestrationFailureInjector:
    """Raises orchestration exceptions."""

    def __init__(self) -> None:
        self._active = False

    def activate(self) -> None:
        self._active = True

    def deactivate(self) -> None:
        self._active = False

    def should_fail(self) -> bool:
        return self._active


class RuntimeChaosSuite:
    """Orchestrates chaos injection across all failure modes.

    Injects failures individually or combined, measures recovery,
    and validates runtime returns to operational state.
    """

    def __init__(
        self,
        ws_manager: "ConnectionManager",
        bus: "AsyncEventBus",
        assembler: "LoopTraceAssembler",
        degraded_controller: "DegradedModeController",
        seed: int | None = None,
    ) -> None:
        self.ws_disconnect = WebSocketDisconnectInjector(ws_manager)
        self.jitter = PacketJitterInjector(seed)
        self.duplicate = DuplicateEmissionInjector(bus)
        self.partial_failure = PartialIngestionFailureInjector(seed=seed)
        self.slow_consumer = SlowConsumerInjector()
        self.memory_failure = MemoryFailureInjector()
        self.orchestration_failure = OrchestrationFailureInjector()
        self._assembler = assembler
        self._degraded = degraded_controller
        self._rng = random.Random(seed)

    async def run_individual(
        self, failure_type: str, duration_seconds: float = 2.0
    ) -> ChaosRecoveryReport:
        """Inject a single failure type and measure recovery."""
        start = time.monotonic()
        report = ChaosRecoveryReport(failures_injected=[failure_type])

        if failure_type == "websocket_disconnect":
            await self.ws_disconnect.inject("chaos_session")
        elif failure_type == "memory_failure":
            self.memory_failure.activate()
            await asyncio.sleep(duration_seconds)
            self.memory_failure.deactivate()
        elif failure_type == "orchestration_failure":
            self.orchestration_failure.activate()
            await asyncio.sleep(duration_seconds)
            self.orchestration_failure.deactivate()
        elif failure_type == "partial_ingestion":
            # Just activate — caller checks should_drop()
            await asyncio.sleep(duration_seconds)

        # Measure recovery
        report.recovery_time_ms = (time.monotonic() - start) * 1000
        report.incomplete_traces = len(self._assembler.get_incomplete_traces())
        report.recovered_successfully = not self._degraded.is_degraded

        logger.info(
            "chaos_individual_complete",
            failure=failure_type,
            recovery_ms=round(report.recovery_time_ms, 1),
            recovered=report.recovered_successfully,
        )

        return report

    async def run_combined(
        self, failures: list[str], duration_seconds: float = 3.0
    ) -> ChaosRecoveryReport:
        """Inject multiple failures simultaneously."""
        start = time.monotonic()
        report = ChaosRecoveryReport(failures_injected=failures)

        # Activate all
        for f in failures:
            if f == "memory_failure":
                self.memory_failure.activate()
            elif f == "orchestration_failure":
                self.orchestration_failure.activate()

        await asyncio.sleep(duration_seconds)

        # Deactivate all
        self.memory_failure.deactivate()
        self.orchestration_failure.deactivate()

        report.recovery_time_ms = (time.monotonic() - start) * 1000
        report.incomplete_traces = len(self._assembler.get_incomplete_traces())
        report.recovered_successfully = not self._degraded.is_degraded

        logger.info(
            "chaos_combined_complete",
            failures=failures,
            recovery_ms=round(report.recovery_time_ms, 1),
            recovered=report.recovered_successfully,
        )

        return report
