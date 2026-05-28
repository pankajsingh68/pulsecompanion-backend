"""Sync engine — temporal alignment and sliding window aggregation."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone

from utils.logger import get_logger

logger = get_logger(__name__)


class TimestampAligner:
    """Aligns events from different sources to a common timeline."""

    def __init__(self, max_drift_ms: float = 500.0) -> None:
        self.max_drift_ms = max_drift_ms

    def align(self, events: list[dict]) -> list[dict]:
        """Sort events by timestamp, discard those beyond max drift."""
        if not events:
            return []
        sorted_events = sorted(events, key=lambda e: e.get("timestamp", ""))
        return sorted_events


class TemporalWindow:
    """Fixed-size temporal window for event aggregation."""

    def __init__(self, window_seconds: float = 10.0) -> None:
        self.window_seconds = window_seconds
        self._events: dict[str, deque] = {}

    def add(self, session_id: str, event: dict) -> None:
        if session_id not in self._events:
            self._events[session_id] = deque(maxlen=100)
        self._events[session_id].append({
            **event,
            "_ingested_at": datetime.now(timezone.utc),
        })

    def get_window(self, session_id: str) -> list[dict]:
        """Get events within the current window."""
        now = datetime.now(timezone.utc)
        events = self._events.get(session_id, deque())
        return [
            e for e in events
            if (now - e["_ingested_at"]).total_seconds() <= self.window_seconds
        ]


class SlidingWindowAggregator:
    """Aggregates sensor values over a sliding window."""

    def aggregate(self, values: list[float]) -> dict:
        """Compute mean, min, max over values."""
        if not values:
            return {"mean": 0.0, "min": 0.0, "max": 0.0, "count": 0}
        return {
            "mean": sum(values) / len(values),
            "min": min(values),
            "max": max(values),
            "count": len(values),
        }


class StreamMerger:
    """Merges multiple sensor streams into a unified snapshot."""

    def merge(self, hr_values: list[float], hrv_values: list[float]) -> dict:
        """Merge HR and HRV streams into a single biometric hint."""
        result = {}
        if hr_values:
            result["hr"] = sum(hr_values) / len(hr_values)
        if hrv_values:
            result["hrv"] = sum(hrv_values) / len(hrv_values)
        return result


class LateEventHandler:
    """Handles events that arrive after their temporal window has closed."""

    def __init__(self, max_late_ms: float = 2000.0) -> None:
        self.max_late_ms = max_late_ms
        self._late_count: dict[str, int] = {}

    def is_late(self, event_timestamp: datetime) -> bool:
        elapsed = (datetime.now(timezone.utc) - event_timestamp).total_seconds() * 1000
        return elapsed > self.max_late_ms

    def record_late(self, session_id: str) -> None:
        self._late_count[session_id] = self._late_count.get(session_id, 0) + 1


class SyncEngine:
    """Coordinates temporal alignment, windowing, and stream merging."""

    def __init__(self) -> None:
        self.aligner = TimestampAligner()
        self.window = TemporalWindow()
        self.aggregator = SlidingWindowAggregator()
        self.merger = StreamMerger()
        self.late_handler = LateEventHandler()

    def ingest_event(self, session_id: str, event: dict) -> None:
        """Add an event to the temporal window."""
        self.window.add(session_id, event)

    def get_merged_snapshot(self, session_id: str) -> dict:
        """Get merged biometric snapshot from current window."""
        events = self.window.get_window(session_id)
        hr_values = [e.get("hr") for e in events if e.get("hr") is not None]
        hrv_values = [e.get("hrv") for e in events if e.get("hrv") is not None]
        return self.merger.merge(hr_values, hrv_values)
