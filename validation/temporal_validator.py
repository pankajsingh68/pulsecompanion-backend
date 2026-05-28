"""Temporal validator — validates timestamp alignment and window boundaries."""

from __future__ import annotations

from utils.logger import get_logger

logger = get_logger(__name__)


class TemporalValidator:
    """Validates temporal alignment and window boundaries.

    Checks: TimestampAligner output within acceptable drift,
    TemporalWindow boundaries respected, late events handled per policy.
    """

    def __init__(self, max_drift_ms: float = 500.0) -> None:
        self.max_drift_ms = max_drift_ms

    def validate_alignment(self, event_ts: float, system_ts: float) -> dict:
        """Validate that an event timestamp is within acceptable drift."""
        drift_ms = abs(event_ts - system_ts) * 1000
        is_valid = drift_ms <= self.max_drift_ms
        return {
            "is_valid": is_valid,
            "drift_ms": round(drift_ms, 2),
            "max_allowed_ms": self.max_drift_ms,
        }

    def validate_window_boundary(
        self, event_ts: float, window_start: float, window_end: float
    ) -> bool:
        """Check if event falls within the expected window."""
        return window_start <= event_ts <= window_end
