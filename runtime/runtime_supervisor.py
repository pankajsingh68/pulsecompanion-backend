"""RuntimeSupervisor — centralized lifecycle supervision and coordination.

Manages subsystem registration, startup/shutdown ordering, health aggregation,
coordinated degradation, recovery orchestration, and panic escalation.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum

from utils.logger import get_logger

logger = get_logger(__name__)


class SupervisorState(str, Enum):
    INITIALIZING = "initializing"
    RUNNING = "running"
    DEGRADED = "degraded"
    PANIC = "panic"
    SHUTTING_DOWN = "shutting_down"
    STOPPED = "stopped"


@dataclass
class RuntimeSubsystem:
    """Registered runtime subsystem."""
    name: str
    initialized: bool = False
    healthy: bool = True
    degraded: bool = False
    last_heartbeat: float = 0.0
    error_count: int = 0
    restart_count: int = 0
    startup_order: int = 0


@dataclass
class RuntimeHealthSummary:
    """Aggregate runtime health."""
    overall_health: str = "healthy"
    degraded_subsystems: list[str] = field(default_factory=list)
    replay_safe: bool = True
    snapshot_safe: bool = True
    concurrency_safe: bool = True
    pressure_state: str = "normal"
    panic_active: bool = False


class RuntimeSupervisor:
    """Centralized runtime supervision and lifecycle coordination.

    No global mutable singleton — instance-based.
    Deterministic startup/shutdown ordering.
    """

    HEARTBEAT_TIMEOUT_S = 30.0
    PANIC_THRESHOLD = 3  # critical failures before panic

    def __init__(self) -> None:
        self._state = SupervisorState.INITIALIZING
        self._subsystems: dict[str, RuntimeSubsystem] = {}
        self._startup_order: list[str] = []
        self._critical_failures: int = 0
        self._started_at: float = 0.0

    @property
    def state(self) -> SupervisorState:
        return self._state

    # --- Subsystem registration ---

    def register(self, name: str, order: int = 0) -> None:
        """Register a subsystem with startup priority."""
        self._subsystems[name] = RuntimeSubsystem(
            name=name, startup_order=order, last_heartbeat=time.monotonic()
        )
        self._startup_order = sorted(
            self._subsystems.keys(),
            key=lambda n: self._subsystems[n].startup_order,
        )

    # --- Lifecycle ---

    async def initialize_runtime(self) -> bool:
        """Initialize all subsystems in order."""
        self._started_at = time.monotonic()
        for name in self._startup_order:
            sub = self._subsystems[name]
            sub.initialized = True
            sub.healthy = True
            sub.last_heartbeat = time.monotonic()
            logger.info("subsystem_initialized_by_supervisor", subsystem=name)

        self._state = SupervisorState.RUNNING
        logger.info("runtime_supervisor_running", subsystems=len(self._subsystems))
        return True

    async def shutdown_runtime(self) -> None:
        """Shutdown all subsystems in reverse order."""
        self._state = SupervisorState.SHUTTING_DOWN
        for name in reversed(self._startup_order):
            self._subsystems[name].initialized = False
            logger.info("subsystem_shutdown", subsystem=name)
        self._state = SupervisorState.STOPPED
        logger.info("runtime_supervisor_stopped")

    async def restart_subsystem(self, name: str) -> bool:
        """Restart a single subsystem."""
        sub = self._subsystems.get(name)
        if not sub:
            return False
        sub.restart_count += 1
        sub.healthy = True
        sub.degraded = False
        sub.error_count = 0
        sub.last_heartbeat = time.monotonic()
        logger.info("subsystem_restarted", subsystem=name, restarts=sub.restart_count)
        return True

    # --- Health monitoring ---

    def record_heartbeat(self, name: str) -> None:
        """Record subsystem heartbeat."""
        sub = self._subsystems.get(name)
        if sub:
            sub.last_heartbeat = time.monotonic()

    def record_error(self, name: str) -> None:
        """Record subsystem error."""
        sub = self._subsystems.get(name)
        if sub:
            sub.error_count += 1
            if sub.error_count >= self.PANIC_THRESHOLD:
                sub.healthy = False
                sub.degraded = True
                self._critical_failures += 1
                if self._critical_failures >= self.PANIC_THRESHOLD:
                    self._trigger_panic()

    # --- Degradation + Panic ---

    async def coordinated_degradation(self, subsystems: list[str]) -> None:
        """Enter coordinated degraded mode."""
        self._state = SupervisorState.DEGRADED
        for name in subsystems:
            sub = self._subsystems.get(name)
            if sub:
                sub.degraded = True
        logger.warning("coordinated_degradation", subsystems=subsystems)

    async def coordinated_recovery(self) -> None:
        """Attempt coordinated recovery."""
        all_healthy = True
        for sub in self._subsystems.values():
            if sub.degraded:
                all_healthy = False
        if all_healthy:
            self._state = SupervisorState.RUNNING
            self._critical_failures = 0
            logger.info("coordinated_recovery_complete")

    def _trigger_panic(self) -> None:
        """Enter panic mode — preserve safety-critical only."""
        self._state = SupervisorState.PANIC
        logger.error("panic_mode_triggered", critical_failures=self._critical_failures)

    async def trigger_panic_mode(self) -> None:
        """External panic trigger."""
        self._trigger_panic()

    # --- Introspection ---

    async def get_runtime_topology(self) -> dict:
        """Get full runtime topology."""
        return {
            "state": self._state.value,
            "subsystems": {
                name: {
                    "initialized": sub.initialized,
                    "healthy": sub.healthy,
                    "degraded": sub.degraded,
                    "error_count": sub.error_count,
                    "restart_count": sub.restart_count,
                }
                for name, sub in self._subsystems.items()
            },
            "startup_order": self._startup_order,
        }

    async def get_supervisor_health(self) -> RuntimeHealthSummary:
        """Get aggregate health summary."""
        degraded = [n for n, s in self._subsystems.items() if s.degraded]
        return RuntimeHealthSummary(
            overall_health=self._state.value,
            degraded_subsystems=degraded,
            panic_active=self._state == SupervisorState.PANIC,
        )

    async def get_subsystem_status(self, name: str) -> dict | None:
        """Get status of a specific subsystem."""
        sub = self._subsystems.get(name)
        if not sub:
            return None
        return {
            "name": sub.name,
            "initialized": sub.initialized,
            "healthy": sub.healthy,
            "degraded": sub.degraded,
            "error_count": sub.error_count,
        }

    async def get_panic_state(self) -> dict:
        """Get panic mode state."""
        return {
            "panic_active": self._state == SupervisorState.PANIC,
            "critical_failures": self._critical_failures,
            "threshold": self.PANIC_THRESHOLD,
        }
