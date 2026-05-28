"""Protection layer — load shedding, backpressure, recompute budgets."""

from __future__ import annotations

from datetime import datetime, timezone

from utils.logger import get_logger

logger = get_logger(__name__)


class LoadShedder:
    """Sheds load when system is overwhelmed."""

    def __init__(self, max_concurrent_sessions: int = 100) -> None:
        self.max_concurrent = max_concurrent_sessions
        self._active: int = 0

    def should_shed(self) -> bool:
        return self._active >= self.max_concurrent

    def increment(self) -> None:
        self._active += 1

    def decrement(self) -> None:
        self._active = max(0, self._active - 1)


class EventBackpressure:
    """Applies backpressure when event queues are too deep."""

    def __init__(self, max_queue_depth: int = 50) -> None:
        self.max_depth = max_queue_depth

    def should_apply(self, queue_depth: int) -> bool:
        return queue_depth >= self.max_depth


class RecomputeBudget:
    """Limits recomputes per second across all sessions."""

    def __init__(self, max_per_second: float = 20.0) -> None:
        self.max_per_second = max_per_second
        self._count: int = 0
        self._window_start: datetime = datetime.now(timezone.utc)

    def can_recompute(self) -> bool:
        now = datetime.now(timezone.utc)
        if (now - self._window_start).total_seconds() >= 1.0:
            self._count = 0
            self._window_start = now
        return self._count < self.max_per_second

    def record(self) -> None:
        self._count += 1


class AdaptiveThrottler:
    """Wraps load shedder, backpressure, and recompute budget."""

    def __init__(self) -> None:
        self.load_shedder = LoadShedder()
        self.backpressure = EventBackpressure()
        self.recompute_budget = RecomputeBudget()

    def should_process(self, queue_depth: int = 0) -> bool:
        if self.load_shedder.should_shed():
            return False
        if self.backpressure.should_apply(queue_depth):
            return False
        if not self.recompute_budget.can_recompute():
            return False
        return True
