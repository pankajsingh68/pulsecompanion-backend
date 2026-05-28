"""LLM Health Monitor — tracks backend health, latency, failures.

Backend unhealthy after 3 consecutive failures OR avg latency > 5s.
Recovery after 2 consecutive successes.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field

from utils.logger import get_logger

logger = get_logger(__name__)

UNHEALTHY_FAILURE_THRESHOLD = 3
UNHEALTHY_LATENCY_THRESHOLD_S = 5.0
RECOVERY_SUCCESS_THRESHOLD = 2


@dataclass
class BackendHealthState:
    """Health state for a single backend."""
    name: str
    healthy: bool = True
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    total_calls: int = 0
    total_failures: int = 0
    last_success_at: float = 0.0
    last_failure_at: float = 0.0
    latency_history: deque = field(default_factory=lambda: deque(maxlen=100))

    @property
    def avg_latency_ms(self) -> float:
        if not self.latency_history:
            return 0.0
        return sum(self.latency_history) / len(self.latency_history)


class LLMHealthMonitor:
    """Monitors health of all registered LLM backends."""

    def __init__(self) -> None:
        self._backends: dict[str, BackendHealthState] = {}

    def register_backend(self, name: str) -> None:
        """Register a backend for health tracking."""
        if name not in self._backends:
            self._backends[name] = BackendHealthState(name=name)

    def record_success(self, name: str, latency_ms: float) -> None:
        """Record a successful completion."""
        state = self._get_or_create(name)
        state.total_calls += 1
        state.consecutive_failures = 0
        state.consecutive_successes += 1
        state.last_success_at = time.monotonic()
        state.latency_history.append(latency_ms)

        # Recovery check
        if not state.healthy and state.consecutive_successes >= RECOVERY_SUCCESS_THRESHOLD:
            state.healthy = True
            logger.info("backend_recovered", backend=name)

    def record_failure(self, name: str) -> None:
        """Record a failed completion."""
        state = self._get_or_create(name)
        state.total_calls += 1
        state.total_failures += 1
        state.consecutive_failures += 1
        state.consecutive_successes = 0
        state.last_failure_at = time.monotonic()

        # Unhealthy check
        if state.consecutive_failures >= UNHEALTHY_FAILURE_THRESHOLD:
            if state.healthy:
                state.healthy = False
                logger.warning("backend_unhealthy", backend=name,
                             failures=state.consecutive_failures)

    def is_healthy(self, name: str) -> bool:
        """Check if a backend is healthy."""
        state = self._backends.get(name)
        if state is None:
            return False

        # Also check latency threshold
        if state.avg_latency_ms > UNHEALTHY_LATENCY_THRESHOLD_S * 1000:
            state.healthy = False
            return False

        return state.healthy

    def get_healthy_backends(self) -> list[str]:
        """Get list of healthy backend names."""
        return [name for name, state in self._backends.items() if state.healthy]

    def get_unhealthy_backends(self) -> list[str]:
        """Get list of unhealthy backend names."""
        return [name for name, state in self._backends.items() if not state.healthy]

    async def get_backend_health(self) -> dict:
        """Introspection: full health report."""
        return {
            name: {
                "healthy": state.healthy,
                "consecutive_failures": state.consecutive_failures,
                "total_calls": state.total_calls,
                "total_failures": state.total_failures,
                "avg_latency_ms": round(state.avg_latency_ms, 2),
            }
            for name, state in self._backends.items()
        }

    def _get_or_create(self, name: str) -> BackendHealthState:
        if name not in self._backends:
            self._backends[name] = BackendHealthState(name=name)
        return self._backends[name]
