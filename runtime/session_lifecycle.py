"""Runtime-native session lifecycle manager.

Tracks per-session state, heartbeat, idle timeout, stale eviction,
recovery transitions, and graceful disconnect handling.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from utils.logger import get_logger

logger = get_logger(__name__)


class SessionState(str, Enum):
    CONNECTING = "connecting"
    ACTIVE = "active"
    DEGRADED = "degraded"
    RECOVERING = "recovering"
    DISCONNECTED = "disconnected"
    EXPIRED = "expired"


@dataclass
class RuntimeSession:
    """Per-session runtime state container."""
    session_id: str
    state: SessionState = SessionState.CONNECTING
    created_at: float = field(default_factory=time.monotonic)
    last_activity_at: float = field(default_factory=time.monotonic)
    last_sensor_update_at: float | None = None
    last_heartbeat_at: float = field(default_factory=time.monotonic)

    # Counters
    lineage_count: int = 0
    orchestration_count: int = 0
    active_traces: int = 0
    memory_writes: int = 0
    stabilization_interventions: int = 0
    websocket_emissions: int = 0

    # Health
    websocket_healthy: bool = True
    is_degraded: bool = False
    recovery_attempts: int = 0
    degraded_subsystems: list[str] = field(default_factory=list)

    # Metrics
    avg_orchestration_interval_ms: float = 0.0
    last_orchestration_at: float | None = None


@dataclass
class SessionHealthReport:
    """Health report for a single session."""
    session_id: str
    state: str
    uptime_seconds: float = 0.0
    idle_seconds: float = 0.0
    lineage_count: int = 0
    websocket_healthy: bool = True
    is_degraded: bool = False
    active_traces: int = 0
    orchestration_frequency_hz: float = 0.0


class SessionLifecycleManager:
    """Manages session lifecycle: creation, heartbeat, degradation, eviction.

    No global mutable singleton — instance-based.
    Deterministic lifecycle transitions.
    """

    IDLE_TIMEOUT_S = 300.0       # 5 min idle → disconnect
    HEARTBEAT_TIMEOUT_S = 90.0   # 90s no heartbeat → stale
    EVICTION_TTL_S = 600.0       # 10 min disconnected → expire

    def __init__(self) -> None:
        self._sessions: dict[str, RuntimeSession] = {}

    # --- Lifecycle transitions ---

    def create_session(self, session_id: str) -> RuntimeSession:
        """Create a new session in CONNECTING state."""
        session = RuntimeSession(session_id=session_id)
        self._sessions[session_id] = session
        logger.info("session_created", session_id=session_id)
        return session

    def activate(self, session_id: str) -> None:
        """Transition session to ACTIVE."""
        session = self._get_or_create(session_id)
        session.state = SessionState.ACTIVE
        session.last_activity_at = time.monotonic()
        logger.info("session_activated", session_id=session_id)

    def mark_degraded(self, session_id: str, subsystems: list[str]) -> None:
        """Transition to DEGRADED state."""
        session = self._get_or_create(session_id)
        session.state = SessionState.DEGRADED
        session.is_degraded = True
        session.degraded_subsystems = subsystems
        logger.info("session_degraded", session_id=session_id, subsystems=subsystems)

    def begin_recovery(self, session_id: str) -> None:
        """Transition to RECOVERING state."""
        session = self._sessions.get(session_id)
        if session:
            session.state = SessionState.RECOVERING
            session.recovery_attempts += 1
            logger.info("session_recovering", session_id=session_id)

    def complete_recovery(self, session_id: str) -> None:
        """Recovery complete → back to ACTIVE."""
        session = self._sessions.get(session_id)
        if session:
            session.state = SessionState.ACTIVE
            session.is_degraded = False
            session.degraded_subsystems = []
            logger.info("session_recovered", session_id=session_id)

    def disconnect(self, session_id: str) -> None:
        """Graceful disconnect."""
        session = self._sessions.get(session_id)
        if session:
            session.state = SessionState.DISCONNECTED
            logger.info("session_disconnected", session_id=session_id)

    # --- Activity tracking ---

    def record_heartbeat(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if session:
            session.last_heartbeat_at = time.monotonic()
            session.last_activity_at = time.monotonic()

    def record_sensor_update(self, session_id: str) -> None:
        session = self._get_or_create(session_id)
        session.last_sensor_update_at = time.monotonic()
        session.last_activity_at = time.monotonic()

    def record_lineage(self, session_id: str) -> None:
        session = self._get_or_create(session_id)
        session.lineage_count += 1

    def record_orchestration(self, session_id: str) -> None:
        session = self._get_or_create(session_id)
        session.orchestration_count += 1
        now = time.monotonic()
        if session.last_orchestration_at:
            interval = (now - session.last_orchestration_at) * 1000
            session.avg_orchestration_interval_ms = (
                0.3 * interval + 0.7 * session.avg_orchestration_interval_ms
            )
        session.last_orchestration_at = now

    def record_ws_emission(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if session:
            session.websocket_emissions += 1

    def record_memory_write(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if session:
            session.memory_writes += 1

    def record_intervention(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if session:
            session.stabilization_interventions += 1

    # --- Health monitoring ---

    def check_all_sessions(self) -> list[str]:
        """Check all sessions for staleness. Returns evicted session IDs."""
        now = time.monotonic()
        evicted: list[str] = []

        for sid, session in list(self._sessions.items()):
            # Heartbeat timeout
            if (session.state == SessionState.ACTIVE
                    and now - session.last_heartbeat_at > self.HEARTBEAT_TIMEOUT_S):
                session.websocket_healthy = False
                self.disconnect(sid)

            # Idle timeout
            if (session.state == SessionState.ACTIVE
                    and now - session.last_activity_at > self.IDLE_TIMEOUT_S):
                self.disconnect(sid)

            # Eviction of disconnected sessions
            if session.state == SessionState.DISCONNECTED:
                disconnect_age = now - session.last_activity_at
                if disconnect_age > self.EVICTION_TTL_S:
                    session.state = SessionState.EXPIRED
                    evicted.append(sid)

        # Remove expired
        for sid in evicted:
            self._sessions.pop(sid, None)
            logger.info("session_evicted", session_id=sid)

        return evicted

    # --- Introspection APIs ---

    async def get_active_sessions(self) -> list[dict]:
        """Get all active session summaries."""
        now = time.monotonic()
        return [
            {
                "session_id": s.session_id,
                "state": s.state.value,
                "uptime_s": round(now - s.created_at, 1),
                "lineage_count": s.lineage_count,
                "is_degraded": s.is_degraded,
            }
            for s in self._sessions.values()
            if s.state not in (SessionState.EXPIRED, SessionState.DISCONNECTED)
        ]

    async def get_session_health(self, session_id: str) -> SessionHealthReport | None:
        """Get health report for a specific session."""
        session = self._sessions.get(session_id)
        if not session:
            return None
        now = time.monotonic()
        freq = 0.0
        if session.avg_orchestration_interval_ms > 0:
            freq = 1000.0 / session.avg_orchestration_interval_ms

        return SessionHealthReport(
            session_id=session_id,
            state=session.state.value,
            uptime_seconds=round(now - session.created_at, 1),
            idle_seconds=round(now - session.last_activity_at, 1),
            lineage_count=session.lineage_count,
            websocket_healthy=session.websocket_healthy,
            is_degraded=session.is_degraded,
            active_traces=session.active_traces,
            orchestration_frequency_hz=round(freq, 2),
        )

    async def get_session_runtime_metrics(self) -> dict:
        """Aggregate runtime metrics across all sessions."""
        total = len(self._sessions)
        active = sum(1 for s in self._sessions.values() if s.state == SessionState.ACTIVE)
        degraded = sum(1 for s in self._sessions.values() if s.is_degraded)
        return {
            "total_sessions": total,
            "active_sessions": active,
            "degraded_sessions": degraded,
            "total_lineages": sum(s.lineage_count for s in self._sessions.values()),
            "total_orchestrations": sum(s.orchestration_count for s in self._sessions.values()),
            "total_interventions": sum(s.stabilization_interventions for s in self._sessions.values()),
        }

    # --- Cleanup ---

    def cleanup_session(self, session_id: str) -> None:
        """Full cleanup: remove session and all references."""
        self._sessions.pop(session_id, None)
        logger.info("session_cleaned", session_id=session_id)

    def _get_or_create(self, session_id: str) -> RuntimeSession:
        if session_id not in self._sessions:
            return self.create_session(session_id)
        return self._sessions[session_id]
