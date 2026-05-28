"""Observability bootstrap — metrics, latency, anomaly detection.

Bootstraps FIRST — all other subsystems depend on observability.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from utils.logger import get_logger

if TYPE_CHECKING:
    from bootstrap.dependency_registry import DependencyRegistry

logger = get_logger(__name__)


class LatencyTracker:
    """Tracks per-operation latency for performance monitoring."""

    def __init__(self) -> None:
        self._records: dict[str, list[float]] = {}

    def record(self, operation: str, latency_ms: float) -> None:
        if operation not in self._records:
            self._records[operation] = []
        self._records[operation].append(latency_ms)
        if len(self._records[operation]) > 200:
            self._records[operation].pop(0)

    def get_avg(self, operation: str) -> float:
        records = self._records.get(operation, [])
        return sum(records) / len(records) if records else 0.0

    def get_p95(self, operation: str) -> float:
        records = sorted(self._records.get(operation, []))
        if not records:
            return 0.0
        idx = int(len(records) * 0.95)
        return records[min(idx, len(records) - 1)]


class StreamMetricsCollector:
    """Collects metrics from biometric streams."""

    def __init__(self) -> None:
        self._counts: dict[str, int] = {}
        self._errors: dict[str, int] = {}

    def record_event(self, session_id: str) -> None:
        self._counts[session_id] = self._counts.get(session_id, 0) + 1

    def record_error(self, session_id: str) -> None:
        self._errors[session_id] = self._errors.get(session_id, 0) + 1

    def get_session_stats(self, session_id: str) -> dict:
        return {
            "events": self._counts.get(session_id, 0),
            "errors": self._errors.get(session_id, 0),
        }


class OrchestrationMetricsCollector:
    """Collects metrics from orchestration recomputes."""

    def __init__(self) -> None:
        self._recompute_count: dict[str, int] = {}
        self._guard_triggers: dict[str, int] = {}

    def record_recompute(self, session_id: str) -> None:
        self._recompute_count[session_id] = self._recompute_count.get(session_id, 0) + 1

    def record_guard_trigger(self, session_id: str) -> None:
        self._guard_triggers[session_id] = self._guard_triggers.get(session_id, 0) + 1

    def get_stats(self, session_id: str) -> dict:
        return {
            "recomputes": self._recompute_count.get(session_id, 0),
            "guard_triggers": self._guard_triggers.get(session_id, 0),
        }


class AnomalyDetector:
    """Detects anomalous patterns in metrics streams."""

    def __init__(self, latency_tracker: LatencyTracker) -> None:
        self.latency_tracker = latency_tracker

    def check_latency_anomaly(self, operation: str, threshold_ms: float = 500.0) -> bool:
        """Returns True if p95 latency exceeds threshold."""
        return self.latency_tracker.get_p95(operation) > threshold_ms

    def check_error_rate(self, errors: int, total: int, threshold: float = 0.1) -> bool:
        """Returns True if error rate exceeds threshold."""
        if total == 0:
            return False
        return (errors / total) > threshold


class MetricsAggregator:
    """Wraps all observability components."""

    def __init__(self) -> None:
        self.latency = LatencyTracker()
        self.streams = StreamMetricsCollector()
        self.orchestration = OrchestrationMetricsCollector()
        self.anomaly = AnomalyDetector(self.latency)


@dataclass
class ObservabilityBundle:
    """All observability components as a typed bundle."""
    metrics: MetricsAggregator
    latency_tracker: LatencyTracker
    stream_metrics: StreamMetricsCollector
    orchestration_metrics: OrchestrationMetricsCollector
    anomaly_detector: AnomalyDetector


def bootstrap_observability(registry: "DependencyRegistry") -> ObservabilityBundle:
    """Initialize all observability components."""
    metrics = MetricsAggregator()

    bundle = ObservabilityBundle(
        metrics=metrics,
        latency_tracker=metrics.latency,
        stream_metrics=metrics.streams,
        orchestration_metrics=metrics.orchestration,
        anomaly_detector=metrics.anomaly,
    )

    registry.register("metrics_aggregator", metrics)
    registry.register("latency_tracker", metrics.latency)
    registry.register("stream_metrics", metrics.streams)
    registry.register("orchestration_metrics", metrics.orchestration)
    registry.register("anomaly_detector", metrics.anomaly)

    logger.info("subsystem_initialized", subsystem="observability", component_count=5)
    return bundle
