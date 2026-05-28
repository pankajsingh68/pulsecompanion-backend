"""Runtime metrics — queue depth, task count, loop rate, memory."""

from __future__ import annotations

import sys


class RuntimeMetrics:
    """Collects runtime-level metrics."""

    def __init__(self) -> None:
        self._loop_iterations: dict[str, int] = {}
        self._task_count: int = 0

    def record_loop_iteration(self, loop_name: str) -> None:
        self._loop_iterations[loop_name] = self._loop_iterations.get(loop_name, 0) + 1

    def set_task_count(self, count: int) -> None:
        self._task_count = count

    def snapshot(self) -> dict:
        return {
            "loop_iterations": dict(self._loop_iterations),
            "task_count": self._task_count,
            "memory_bytes": sys.getsizeof(self._loop_iterations),
        }

    def reset(self) -> None:
        self._loop_iterations.clear()
        self._task_count = 0
