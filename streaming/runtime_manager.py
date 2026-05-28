"""Runtime manager — wires all streaming components together."""

from __future__ import annotations

from typing import TYPE_CHECKING

from utils.logger import get_logger

if TYPE_CHECKING:
    from bootstrap.observability_bootstrap import LatencyTracker
    from orchestration.orchestrator import UXOrchestrator
    from runtime.session_runtime import SessionRuntime
    from stability.debounce import OrchestratorDebouncer
    from stability.hysteresis import ModeHysteresis
    from streaming.ingestion import SensorIngestionPipeline
    from websocket.manager import ConnectionManager

logger = get_logger(__name__)


class RuntimeStateStore:
    """Stores runtime state per session."""

    def __init__(self) -> None:
        self._states: dict[str, dict] = {}

    def update(self, session_id: str, state: dict) -> None:
        self._states[session_id] = state

    def get(self, session_id: str) -> dict:
        return self._states.get(session_id, {})


class StreamScheduler:
    """Schedules stream processing tasks."""

    def __init__(self) -> None:
        self._schedules: dict[str, float] = {}

    def set_interval(self, session_id: str, interval_s: float) -> None:
        self._schedules[session_id] = interval_s

    def get_interval(self, session_id: str) -> float:
        return self._schedules.get(session_id, 5.0)


class AdaptiveLoopController:
    """Controls the adaptive processing loop frequency."""

    def __init__(self) -> None:
        self._active: dict[str, bool] = {}

    def activate(self, session_id: str) -> None:
        self._active[session_id] = True

    def deactivate(self, session_id: str) -> None:
        self._active[session_id] = False

    def is_active(self, session_id: str) -> bool:
        return self._active.get(session_id, False)


class RuntimeManager:
    """Wires all runtime components together.

    Receives: ingestion_pipeline, orchestrator, ws_manager,
    session_runtime, debouncer, hysteresis, scheduler, loop_controller.
    """

    def __init__(
        self,
        ingestion_pipeline: "SensorIngestionPipeline",
        orchestrator: "UXOrchestrator",
        ws_manager: "ConnectionManager",
        session_runtime: "SessionRuntime",
        debouncer: "OrchestratorDebouncer",
        hysteresis: "ModeHysteresis",
        latency_tracker: "LatencyTracker",
    ) -> None:
        self.ingestion = ingestion_pipeline
        self.orchestrator = orchestrator
        self.ws_manager = ws_manager
        self.session_runtime = session_runtime
        self.debouncer = debouncer
        self.hysteresis = hysteresis
        self.latency_tracker = latency_tracker
        self.state_store = RuntimeStateStore()
        self.scheduler = StreamScheduler()
        self.loop_controller = AdaptiveLoopController()

    def get_session_status(self, session_id: str) -> dict:
        return {
            "is_active": self.loop_controller.is_active(session_id),
            "interval": self.scheduler.get_interval(session_id),
            "state": self.state_store.get(session_id),
        }
