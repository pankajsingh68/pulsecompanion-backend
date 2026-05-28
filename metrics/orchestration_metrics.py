"""Orchestration metrics — transitions, recomputes, confidence, oscillations."""

from __future__ import annotations


class OrchestrationMetrics:
    """Collects orchestration-level metrics."""

    def __init__(self) -> None:
        self._transitions: int = 0
        self._recomputes: int = 0
        self._guard_triggers: int = 0
        self._oscillations: int = 0
        self._confidence_values: list[float] = []
        self._degraded_seconds: float = 0.0

    def record_transition(self) -> None:
        self._transitions += 1

    def record_recompute(self) -> None:
        self._recomputes += 1

    def record_guard_trigger(self) -> None:
        self._guard_triggers += 1

    def record_oscillation(self) -> None:
        self._oscillations += 1

    def record_confidence(self, value: float) -> None:
        self._confidence_values.append(value)
        if len(self._confidence_values) > 100:
            self._confidence_values.pop(0)

    def snapshot(self) -> dict:
        avg_conf = (
            sum(self._confidence_values) / len(self._confidence_values)
            if self._confidence_values else 0.0
        )
        return {
            "transitions": self._transitions,
            "recomputes": self._recomputes,
            "guard_triggers": self._guard_triggers,
            "oscillations": self._oscillations,
            "avg_confidence": round(avg_conf, 3),
            "degraded_seconds": self._degraded_seconds,
        }

    def reset(self) -> None:
        self._transitions = 0
        self._recomputes = 0
        self._guard_triggers = 0
        self._oscillations = 0
        self._confidence_values.clear()
        self._degraded_seconds = 0.0
