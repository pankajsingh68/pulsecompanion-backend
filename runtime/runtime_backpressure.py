"""Runtime-native backpressure and adaptive load shedding.

Prevents runtime collapse under high throughput, slow consumers,
or orchestration overload. Implements event coalescing and bounded queues.

Fixes applied:
- Task 1: Coalesce buffer TTL eviction (no memory leak)
- Task 2: Stable rolling-window EPS (no divide-by-near-zero)
- Task 3: Queue aging detection (old events trigger escalation)
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum

from utils.logger import get_logger

logger = get_logger(__name__)


class BackpressureState(str, Enum):
    NORMAL = "normal"
    ELEVATED = "elevated"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class LoadSheddingPolicy:
    """Configurable thresholds for load shedding."""
    elevated_queue_depth: int = 30
    high_queue_depth: int = 60
    critical_queue_depth: int = 90
    elevated_latency_ms: float = 100.0
    high_latency_ms: float = 300.0
    critical_latency_ms: float = 500.0
    elevated_age_ms: float = 250.0
    high_age_ms: float = 1000.0
    critical_age_ms: float = 2500.0
    max_events_per_second: float = 100.0
    coalesce_window_ms: float = 50.0
    recovery_hold_seconds: float = 5.0


# Task 1: Coalesce buffer TTL
COALESCE_TTL_S = 60.0
# Task 2: Minimum EPS window to prevent divide-by-near-zero
MIN_EPS_WINDOW_S = 0.25


@dataclass
class BackpressureMetrics:
    """Metrics for backpressure monitoring."""
    events_dropped: int = 0
    websocket_messages_suppressed: int = 0
    coalesced_updates: int = 0
    overload_duration_ms: float = 0.0
    current_state: BackpressureState = BackpressureState.NORMAL
    queue_depth: int = 0
    processing_latency_ms: float = 0.0
    events_per_second: float = 0.0
    stale_buffers_evicted: int = 0
    active_coalesced_sessions: int = 0
    queue_age_ms: float = 0.0


class RuntimeBackpressureController:
    """Controls adaptive load shedding and event coalescing.

    Monitors queue depths, throughput, latency, and queue age.
    Sheds load progressively: NORMAL → ELEVATED → HIGH → CRITICAL.
    Critical events are never dropped.
    """

    def __init__(self, policy: LoadSheddingPolicy | None = None) -> None:
        self._policy = policy or LoadSheddingPolicy()
        self._state = BackpressureState.NORMAL
        self._state_entered_at: float = time.monotonic()
        self._metrics = BackpressureMetrics()

        # Tracking
        self._queue_depth: int = 0
        self._latency_ema: float = 0.0
        self._event_timestamps: deque = deque(maxlen=200)
        self._coalesce_buffer: dict[str, dict] = {}
        self._coalesce_timestamps: dict[str, float] = {}
        # Task 3: Queue age tracking
        self._queue_age_ema: float = 0.0
        self._oldest_event_age_ms: float = 0.0

    @property
    def state(self) -> BackpressureState:
        return self._state

    # --- Metric recording ---

    def record_queue_depth(self, depth: int) -> None:
        """Update current queue depth."""
        self._queue_depth = depth
        self._metrics.queue_depth = depth
        self._evaluate()

    def record_processing_latency(self, latency_ms: float) -> None:
        """Update processing latency (EMA)."""
        if self._latency_ema == 0:
            self._latency_ema = latency_ms
        else:
            self._latency_ema = 0.3 * latency_ms + 0.7 * self._latency_ema
        self._metrics.processing_latency_ms = round(self._latency_ema, 2)
        self._evaluate()

    def record_event(self) -> None:
        """Record an event arrival for throughput calculation."""
        self._event_timestamps.append(time.monotonic())

    def record_queue_age(self, age_ms: float) -> None:
        """Record the age of the oldest event in queue (Task 3)."""
        self._oldest_event_age_ms = age_ms
        if self._queue_age_ema == 0:
            self._queue_age_ema = age_ms
        else:
            self._queue_age_ema = 0.3 * age_ms + 0.7 * self._queue_age_ema
        self._metrics.queue_age_ms = round(self._queue_age_ema, 2)
        self._evaluate()

    # --- Load shedding decisions ---

    def should_shed(self, event_type: str, is_critical: bool = False) -> bool:
        """Determine if an event should be shed (dropped).
        Critical events are NEVER dropped."""
        if is_critical:
            return False
        if self._state == BackpressureState.CRITICAL:
            self._metrics.events_dropped += 1
            return True
        if self._state == BackpressureState.HIGH:
            low_priority = ["introspection", "metrics", "debug"]
            if any(lp in event_type for lp in low_priority):
                self._metrics.events_dropped += 1
                return True
        return False

    def should_suppress_websocket(self, is_safety: bool = False) -> bool:
        if is_safety:
            return False
        if self._state in (BackpressureState.HIGH, BackpressureState.CRITICAL):
            self._metrics.websocket_messages_suppressed += 1
            return True
        return False

    def should_reduce_orchestration(self) -> bool:
        return self._state in (BackpressureState.HIGH, BackpressureState.CRITICAL)

    def should_suppress_memory_write(self, is_essential: bool = False) -> bool:
        if is_essential:
            return False
        return self._state == BackpressureState.CRITICAL

    # --- Event coalescing ---

    def coalesce_event(self, session_id: str, event: dict) -> dict | None:
        """Coalesce rapid events within a time window."""
        now = time.monotonic()
        last_time = self._coalesce_timestamps.get(session_id, 0)
        window_s = self._policy.coalesce_window_ms / 1000.0

        if now - last_time < window_s:
            existing = self._coalesce_buffer.get(session_id, {})
            existing.update(event)
            self._coalesce_buffer[session_id] = existing
            self._metrics.coalesced_updates += 1
            return None

        merged = self._coalesce_buffer.pop(session_id, {})
        merged.update(event)
        self._coalesce_timestamps[session_id] = now
        return merged

    # --- Task 1: Coalesce buffer cleanup ---

    def cleanup_stale_coalesced(self) -> int:
        """Evict stale coalesced session buffers (Task 1).
        Returns number evicted. Bounded, non-blocking."""
        now = time.monotonic()
        stale_sessions: list[str] = []

        for sid, ts in self._coalesce_timestamps.items():
            if now - ts > COALESCE_TTL_S:
                stale_sessions.append(sid)

        for sid in stale_sessions:
            self._coalesce_buffer.pop(sid, None)
            self._coalesce_timestamps.pop(sid, None)

        evicted = len(stale_sessions)
        if evicted > 0:
            self._metrics.stale_buffers_evicted += evicted
            logger.info("backpressure_coalesce_cleanup", evicted=evicted)

        self._metrics.active_coalesced_sessions = len(self._coalesce_timestamps)
        return evicted

    # --- State management ---

    def current_state(self) -> dict:
        """Get current backpressure state."""
        return {
            "state": self._state.value,
            "queue_depth": self._queue_depth,
            "latency_ms": round(self._latency_ema, 2),
            "queue_age_ms": round(self._queue_age_ema, 2),
            "events_per_second": round(self._compute_eps(), 2),
            "metrics": {
                "events_dropped": self._metrics.events_dropped,
                "ws_suppressed": self._metrics.websocket_messages_suppressed,
                "coalesced": self._metrics.coalesced_updates,
                "stale_evicted": self._metrics.stale_buffers_evicted,
                "active_coalesced": self._metrics.active_coalesced_sessions,
            },
        }

    def _evaluate(self) -> None:
        """Re-evaluate pressure state based on current metrics."""
        new_state = self._compute_state()

        if self._is_de_escalation(new_state):
            elapsed = time.monotonic() - self._state_entered_at
            if elapsed < self._policy.recovery_hold_seconds:
                return

        if new_state != self._state:
            old = self._state
            self._state = new_state
            self._state_entered_at = time.monotonic()
            self._metrics.current_state = new_state
            logger.info(
                "backpressure_transition",
                old=old.value, new=new_state.value,
                queue=self._queue_depth,
                latency=round(self._latency_ema, 1),
                queue_age=round(self._queue_age_ema, 1),
            )

    def _compute_state(self) -> BackpressureState:
        """Determine state from queue depth, latency, AND queue age (Task 3)."""
        p = self._policy
        # CRITICAL: any metric at critical threshold
        if (self._queue_depth >= p.critical_queue_depth
                or self._latency_ema >= p.critical_latency_ms
                or self._queue_age_ema >= p.critical_age_ms):
            return BackpressureState.CRITICAL
        # HIGH
        if (self._queue_depth >= p.high_queue_depth
                or self._latency_ema >= p.high_latency_ms
                or self._queue_age_ema >= p.high_age_ms):
            return BackpressureState.HIGH
        # ELEVATED
        if (self._queue_depth >= p.elevated_queue_depth
                or self._latency_ema >= p.elevated_latency_ms
                or self._queue_age_ema >= p.elevated_age_ms):
            return BackpressureState.ELEVATED
        return BackpressureState.NORMAL

    def _is_de_escalation(self, new: BackpressureState) -> bool:
        order = [BackpressureState.NORMAL, BackpressureState.ELEVATED,
                 BackpressureState.HIGH, BackpressureState.CRITICAL]
        return order.index(new) < order.index(self._state)

    def _compute_eps(self) -> float:
        """Compute events per second with stable rolling window (Task 2).
        Clamps window to MIN_EPS_WINDOW_S to prevent divide-by-near-zero."""
        if len(self._event_timestamps) < 2:
            return 0.0
        window = self._event_timestamps[-1] - self._event_timestamps[0]
        # Task 2: clamp minimum window
        window = max(window, MIN_EPS_WINDOW_S)
        eps = len(self._event_timestamps) / window
        self._metrics.events_per_second = round(eps, 2)
        return eps
