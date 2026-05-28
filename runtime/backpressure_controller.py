"""Adaptive backpressure controller — flow control for the adaptive pipeline.

Tracks queue depths, processing latency, and drop rates across subsystems.
Escalates pressure levels and adjusts runtime behavior accordingly.
Recovery hysteresis prevents premature de-escalation.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from utils.helpers import clamp
from utils.logger import get_logger

if TYPE_CHECKING:
    from events.event_bus import AsyncEventBus

logger = get_logger(__name__)


class PressureLevel(str, Enum):
    NORMAL = "normal"
    ELEVATED = "elevated"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class QueuePressureSnapshot:
    """Point-in-time snapshot of all queue pressures."""
    timestamp: float = field(default_factory=time.monotonic)
    websocket_queue_depth: int = 0
    event_bus_pending: int = 0
    memory_persistence_backlog: int = 0
    orchestration_recompute_hz: float = 0.0
    avg_processing_latency_ms: float = 0.0
    dropped_events: int = 0
    pressure_level: PressureLevel = PressureLevel.NORMAL
    pressure_score: float = 0.0  # 0.0–1.0 composite


# Thresholds for pressure escalation
_THRESHOLDS = {
    PressureLevel.ELEVATED: 0.4,
    PressureLevel.HIGH: 0.65,
    PressureLevel.CRITICAL: 0.85,
}

# Recovery must drop below these to de-escalate (hysteresis)
_RECOVERY_THRESHOLDS = {
    PressureLevel.ELEVATED: 0.25,
    PressureLevel.HIGH: 0.45,
    PressureLevel.CRITICAL: 0.60,
}

# Minimum time at a level before de-escalation allowed
_MIN_HOLD_SECONDS = 5.0


class AdaptiveBackpressureController:
    """Controls adaptive pipeline flow based on system pressure.

    Tracks queue depths, latency, and drops. Escalates/de-escalates
    pressure levels with recovery hysteresis.

    Behavior by level:
    - NORMAL: full adaptive pipeline
    - ELEVATED: reduce orchestration + websocket frequency
    - HIGH: suppress noncritical memory writes, disable expensive recomputes
    - CRITICAL: freeze recomputation, emit only safety-critical, hold last-known-good
    """

    # Weights for composite pressure score
    WEIGHTS = {
        "websocket_queue": 0.25,
        "event_bus": 0.20,
        "memory_backlog": 0.15,
        "recompute_freq": 0.15,
        "latency": 0.15,
        "drops": 0.10,
    }

    # Capacity limits (normalize against these)
    MAX_WS_QUEUE = 50
    MAX_BUS_PENDING = 100
    MAX_MEMORY_BACKLOG = 30
    MAX_RECOMPUTE_HZ = 20.0
    MAX_LATENCY_MS = 500.0
    MAX_DROPS_PER_WINDOW = 50

    def __init__(self, bus: "AsyncEventBus | None" = None) -> None:
        self._bus = bus
        self._level = PressureLevel.NORMAL
        self._level_entered_at: float = time.monotonic()
        self._history: list[QueuePressureSnapshot] = []
        self._dropped_total: int = 0
        self._last_snapshot: QueuePressureSnapshot | None = None

        # Tracked counters (updated externally)
        self._ws_queue_depth: int = 0
        self._bus_pending: int = 0
        self._memory_backlog: int = 0
        self._recompute_hz: float = 0.0
        self._avg_latency_ms: float = 0.0
        self._drops_in_window: int = 0

    @property
    def level(self) -> PressureLevel:
        return self._level

    @property
    def is_critical(self) -> bool:
        return self._level == PressureLevel.CRITICAL

    # --- External metric updates ---

    def update_ws_queue(self, depth: int) -> None:
        self._ws_queue_depth = depth

    def update_bus_pending(self, count: int) -> None:
        self._bus_pending = count

    def update_memory_backlog(self, count: int) -> None:
        self._memory_backlog = count

    def update_recompute_frequency(self, hz: float) -> None:
        self._recompute_hz = hz

    def update_latency(self, latency_ms: float) -> None:
        # EMA for latency
        if self._avg_latency_ms == 0:
            self._avg_latency_ms = latency_ms
        else:
            self._avg_latency_ms = 0.3 * latency_ms + 0.7 * self._avg_latency_ms

    def record_drop(self) -> None:
        self._drops_in_window += 1
        self._dropped_total += 1

    # --- Core evaluation ---

    def evaluate(self) -> QueuePressureSnapshot:
        """Evaluate current pressure and potentially transition levels.

        Call this periodically (e.g., every 1s or after each pipeline cycle).
        Returns the current pressure snapshot.
        """
        score = self._compute_pressure_score()
        new_level = self._determine_level(score)

        # Apply hysteresis for de-escalation
        if self._is_de_escalation(new_level):
            if not self._can_de_escalate(score):
                new_level = self._level  # hold current level

        # Transition if changed
        if new_level != self._level:
            old_level = self._level
            self._level = new_level
            self._level_entered_at = time.monotonic()
            self._emit_transition(old_level, new_level, score)

        snapshot = QueuePressureSnapshot(
            websocket_queue_depth=self._ws_queue_depth,
            event_bus_pending=self._bus_pending,
            memory_persistence_backlog=self._memory_backlog,
            orchestration_recompute_hz=round(self._recompute_hz, 2),
            avg_processing_latency_ms=round(self._avg_latency_ms, 2),
            dropped_events=self._drops_in_window,
            pressure_level=self._level,
            pressure_score=round(score, 3),
        )

        self._last_snapshot = snapshot
        self._history.append(snapshot)
        if len(self._history) > 100:
            self._history.pop(0)

        # Reset window counters
        self._drops_in_window = 0

        return snapshot

    def _compute_pressure_score(self) -> float:
        """Compute composite pressure score 0.0–1.0."""
        ws_pressure = min(self._ws_queue_depth / self.MAX_WS_QUEUE, 1.0)
        bus_pressure = min(self._bus_pending / self.MAX_BUS_PENDING, 1.0)
        mem_pressure = min(self._memory_backlog / self.MAX_MEMORY_BACKLOG, 1.0)
        recompute_pressure = min(self._recompute_hz / self.MAX_RECOMPUTE_HZ, 1.0)
        latency_pressure = min(self._avg_latency_ms / self.MAX_LATENCY_MS, 1.0)
        drop_pressure = min(self._drops_in_window / self.MAX_DROPS_PER_WINDOW, 1.0)

        score = (
            ws_pressure * self.WEIGHTS["websocket_queue"]
            + bus_pressure * self.WEIGHTS["event_bus"]
            + mem_pressure * self.WEIGHTS["memory_backlog"]
            + recompute_pressure * self.WEIGHTS["recompute_freq"]
            + latency_pressure * self.WEIGHTS["latency"]
            + drop_pressure * self.WEIGHTS["drops"]
        )
        return clamp(score)

    def _determine_level(self, score: float) -> PressureLevel:
        """Determine pressure level from score (escalation only uses thresholds)."""
        if score >= _THRESHOLDS[PressureLevel.CRITICAL]:
            return PressureLevel.CRITICAL
        if score >= _THRESHOLDS[PressureLevel.HIGH]:
            return PressureLevel.HIGH
        if score >= _THRESHOLDS[PressureLevel.ELEVATED]:
            return PressureLevel.ELEVATED
        return PressureLevel.NORMAL

    def _is_de_escalation(self, new_level: PressureLevel) -> bool:
        """Check if proposed transition is a de-escalation."""
        order = [PressureLevel.NORMAL, PressureLevel.ELEVATED,
                 PressureLevel.HIGH, PressureLevel.CRITICAL]
        return order.index(new_level) < order.index(self._level)

    def _can_de_escalate(self, score: float) -> bool:
        """Check if de-escalation is allowed (hysteresis + hold time)."""
        # Must hold current level for minimum time
        elapsed = time.monotonic() - self._level_entered_at
        if elapsed < _MIN_HOLD_SECONDS:
            return False

        # Score must drop below recovery threshold for current level
        recovery_threshold = _RECOVERY_THRESHOLDS.get(self._level, 0.0)
        return score < recovery_threshold

    def _emit_transition(
        self, old: PressureLevel, new: PressureLevel, score: float
    ) -> None:
        """Emit pressure transition event (fire-and-forget, never crashes)."""
        logger.info(
            "pressure_level_changed",
            old_level=old.value,
            new_level=new.value,
            score=round(score, 3),
        )
        # Bus emission would go here if bus is available
        # Wrapped to never crash runtime

    # --- Policy queries (used by pipeline stages) ---

    def should_orchestrate(self) -> bool:
        """Should orchestration recompute proceed?"""
        return self._level not in (PressureLevel.CRITICAL,)

    def should_emit_websocket(self, is_safety_critical: bool = False) -> bool:
        """Should this websocket emission proceed?"""
        if is_safety_critical:
            return True  # always emit safety-critical
        return self._level != PressureLevel.CRITICAL

    def should_persist_memory(self, is_critical: bool = False) -> bool:
        """Should this memory write proceed?"""
        if is_critical:
            return True
        return self._level not in (PressureLevel.HIGH, PressureLevel.CRITICAL)

    def should_recompute(self) -> bool:
        """Should expensive recomputation proceed?"""
        return self._level in (PressureLevel.NORMAL, PressureLevel.ELEVATED)

    def get_orchestration_interval_multiplier(self) -> float:
        """Multiplier for orchestration interval (higher = slower)."""
        if self._level == PressureLevel.ELEVATED:
            return 2.0
        if self._level == PressureLevel.HIGH:
            return 4.0
        if self._level == PressureLevel.CRITICAL:
            return float("inf")  # frozen
        return 1.0

    def get_ws_emission_interval_multiplier(self) -> float:
        """Multiplier for websocket emission interval."""
        if self._level == PressureLevel.ELEVATED:
            return 1.5
        if self._level == PressureLevel.HIGH:
            return 3.0
        if self._level == PressureLevel.CRITICAL:
            return float("inf")
        return 1.0

    # --- Introspection APIs ---

    async def get_backpressure_state(self) -> dict:
        """Read-only introspection: current backpressure state."""
        return {
            "level": self._level.value,
            "score": round(self._compute_pressure_score(), 3),
            "level_duration_s": round(time.monotonic() - self._level_entered_at, 1),
            "dropped_total": self._dropped_total,
            "can_orchestrate": self.should_orchestrate(),
            "can_emit_ws": self.should_emit_websocket(),
            "can_persist": self.should_persist_memory(),
            "can_recompute": self.should_recompute(),
        }

    async def get_queue_depths(self) -> dict:
        """Read-only introspection: current queue depths."""
        return {
            "websocket": self._ws_queue_depth,
            "event_bus": self._bus_pending,
            "memory_backlog": self._memory_backlog,
        }

    async def get_drop_rate(self) -> dict:
        """Read-only introspection: drop statistics."""
        return {
            "total_dropped": self._dropped_total,
            "current_window_drops": self._drops_in_window,
            "avg_latency_ms": round(self._avg_latency_ms, 2),
        }

    def get_history(self, n: int = 10) -> list[QueuePressureSnapshot]:
        """Get recent pressure history."""
        return self._history[-n:]
