"""Degraded mode controller — real operational degradation state machine.

Manages subsystem health, degraded mode transitions, recovery,
and fallback orchestration. Emits degraded_mode.changed events.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING

from utils.logger import get_logger

if TYPE_CHECKING:
    from events.event_bus import AsyncEventBus
    from events.lineage import LineageContext
    from events.runtime_emitters import DegradedModeEmitter

logger = get_logger(__name__)


class SubsystemHealth(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


@dataclass
class DegradedRuntimeState:
    """Current degraded mode state."""
    active: bool = False
    affected_subsystems: list[str] = field(default_factory=list)
    entered_at: float = 0.0
    recovery_attempts: int = 0
    last_known_good_state: dict | None = None
    reason: str = ""
    recovery_budget_ms: float = 5000.0


@dataclass
class SubsystemStatus:
    """Health status of a single subsystem."""
    name: str
    health: SubsystemHealth = SubsystemHealth.HEALTHY
    last_success_at: float = 0.0
    consecutive_failures: int = 0
    last_error: str | None = None


class DegradedModeController:
    """Controls runtime degradation state machine.

    Monitors subsystem health, enters/exits degraded mode,
    manages recovery, and preserves last-known-good state.
    No global mutable singleton state — instance-based.
    """

    FAILURE_THRESHOLD = 3  # consecutive failures before degraded
    RECOVERY_THRESHOLD = 2  # consecutive successes before recovery

    def __init__(self, emitter: "DegradedModeEmitter | None" = None) -> None:
        self._emitter = emitter
        self._state = DegradedRuntimeState()
        self._subsystems: dict[str, SubsystemStatus] = {}
        self._recovery_successes: dict[str, int] = {}

        # Register known subsystems
        for name in [
            "websocket", "memory", "orchestration",
            "sensor_ingestion", "event_bus", "confidence",
        ]:
            self._subsystems[name] = SubsystemStatus(
                name=name, last_success_at=time.monotonic()
            )

    @property
    def is_degraded(self) -> bool:
        return self._state.active

    @property
    def current_state(self) -> DegradedRuntimeState:
        return self._state

    def record_success(self, subsystem: str) -> None:
        """Record a successful operation for a subsystem."""
        status = self._subsystems.get(subsystem)
        if status is None:
            status = SubsystemStatus(name=subsystem)
            self._subsystems[subsystem] = status

        status.last_success_at = time.monotonic()
        status.consecutive_failures = 0
        status.health = SubsystemHealth.HEALTHY

        # Track recovery
        self._recovery_successes[subsystem] = (
            self._recovery_successes.get(subsystem, 0) + 1
        )

        # Check if we can exit degraded mode
        if self._state.active and subsystem in self._state.affected_subsystems:
            if self._recovery_successes.get(subsystem, 0) >= self.RECOVERY_THRESHOLD:
                self._state.affected_subsystems.remove(subsystem)
                if not self._state.affected_subsystems:
                    self._exit_degraded_mode()

    def record_failure(self, subsystem: str, error: str = "") -> None:
        """Record a failure for a subsystem."""
        status = self._subsystems.get(subsystem)
        if status is None:
            status = SubsystemStatus(name=subsystem)
            self._subsystems[subsystem] = status

        status.consecutive_failures += 1
        status.last_error = error
        self._recovery_successes[subsystem] = 0

        if status.consecutive_failures >= self.FAILURE_THRESHOLD:
            status.health = SubsystemHealth.DEGRADED
            self._enter_degraded_mode(subsystem, error)

    async def record_failure_async(
        self, subsystem: str, error: str = "",
        lineage: "LineageContext | None" = None,
    ) -> None:
        """Async version that also emits degraded_mode.changed event."""
        was_degraded = self._state.active
        self.record_failure(subsystem, error)

        if not was_degraded and self._state.active and self._emitter and lineage:
            await self._emitter.emit(
                lineage, "normal", "degraded",
                self._state.reason, self._state.affected_subsystems,
            )

    async def record_success_async(
        self, subsystem: str, lineage: "LineageContext | None" = None,
    ) -> None:
        """Async version that emits recovery event."""
        was_degraded = self._state.active
        self.record_success(subsystem)

        if was_degraded and not self._state.active and self._emitter and lineage:
            await self._emitter.emit(
                lineage, "degraded", "normal",
                "all_subsystems_recovered", [],
            )

    def set_last_known_good_state(self, state: dict) -> None:
        """Preserve last-known-good emotional state for fallback."""
        self._state.last_known_good_state = dict(state)

    def get_fallback_state(self) -> dict:
        """Get last-known-good state for fallback during degradation."""
        if self._state.last_known_good_state:
            return dict(self._state.last_known_good_state)
        # Safe default — prevents impossible emotional outputs
        return {
            "stress": 0.3, "fatigue": 0.3, "focus": 0.5,
            "ux_mode": "normal", "confidence": 0.3,
            "engagement": 0.5, "cognitive_load": 0.4,
        }

    def get_subsystem_health(self) -> dict[str, str]:
        """Get health status of all subsystems."""
        return {
            name: status.health.value
            for name, status in self._subsystems.items()
        }

    def get_metrics(self) -> dict:
        """Get degraded mode metrics."""
        return {
            "is_degraded": self._state.active,
            "affected_subsystems": self._state.affected_subsystems,
            "recovery_attempts": self._state.recovery_attempts,
            "degraded_duration_s": (
                time.monotonic() - self._state.entered_at
                if self._state.active else 0.0
            ),
            "subsystem_health": self.get_subsystem_health(),
        }

    def _enter_degraded_mode(self, subsystem: str, reason: str) -> None:
        """Enter degraded mode."""
        if not self._state.active:
            self._state.active = True
            self._state.entered_at = time.monotonic()
            self._state.reason = reason
            logger.warning(
                "degraded_mode_entered",
                subsystem=subsystem, reason=reason,
            )

        if subsystem not in self._state.affected_subsystems:
            self._state.affected_subsystems.append(subsystem)

    def _exit_degraded_mode(self) -> None:
        """Exit degraded mode — all subsystems recovered."""
        self._state.active = False
        self._state.recovery_attempts += 1
        duration = time.monotonic() - self._state.entered_at
        logger.info(
            "degraded_mode_exited",
            duration_s=round(duration, 2),
            recovery_attempts=self._state.recovery_attempts,
        )
