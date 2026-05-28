"""Ambient awareness loop — continuous background state monitoring."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from utils.logger import get_logger

if TYPE_CHECKING:
    from events.event_store import EventStore
    from events.state_timeline import StateTimeline
    from safety.transition_guard import TransitionGuard
    from streaming.recompute_engine import RecomputeEngine
    from websocket.manager import ConnectionManager

logger = get_logger(__name__)


class FatigueDetector:
    """Detects rising fatigue trends."""

    def detect(self, stress_trend: list[float]) -> bool:
        if len(stress_trend) < 3:
            return False
        return stress_trend[-1] > stress_trend[0] + 0.15


class RecoveryDetector:
    """Detects recovery (stress dropping)."""

    def detect(self, stress_trend: list[float]) -> bool:
        if len(stress_trend) < 3:
            return False
        return stress_trend[-1] < stress_trend[0] - 0.15


class AmbientTransitionDetector:
    """Detects ambient state transitions that warrant proactive action."""

    def __init__(self) -> None:
        self.fatigue = FatigueDetector()
        self.recovery = RecoveryDetector()

    def detect(self, stress_trend: list[float]) -> str | None:
        if self.fatigue.detect(stress_trend):
            return "fatigue_rising"
        if self.recovery.detect(stress_trend):
            return "recovery_detected"
        return None


class AmbientStateMonitor:
    """Monitors state timeline for ambient transitions."""

    def __init__(self, state_timeline: "StateTimeline", event_store: "EventStore") -> None:
        self.state_timeline = state_timeline
        self.event_store = event_store
        self.detector = AmbientTransitionDetector()

    def check_session(self, session_id: str) -> str | None:
        trend = self.state_timeline.get_stress_trend(session_id, 5)
        return self.detector.detect(trend)


class AmbientAwarenessLoop:
    """Background loop that monitors all active sessions for ambient transitions."""

    def __init__(
        self,
        state_timeline: "StateTimeline",
        event_store: "EventStore",
        recompute_engine: "RecomputeEngine",
        ws_manager: "ConnectionManager",
        transition_guard: "TransitionGuard",
    ) -> None:
        self.monitor = AmbientStateMonitor(state_timeline, event_store)
        self.recompute_engine = recompute_engine
        self.ws_manager = ws_manager
        self.transition_guard = transition_guard
        self._task: asyncio.Task | None = None

    async def start(self, interval_seconds: float = 10.0) -> None:
        """Start the ambient awareness loop."""
        self._task = asyncio.create_task(self._run(interval_seconds))
        logger.info("ambient_loop_started", interval=interval_seconds)

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("ambient_loop_stopped")

    async def _run(self, interval: float) -> None:
        try:
            while True:
                await asyncio.sleep(interval)
                # Monitor would check active sessions here
                logger.debug("ambient_loop_tick")
        except asyncio.CancelledError:
            logger.info("ambient_loop_cancelled")
            return
