"""Degradation layer — graceful degradation when sensors fail."""

from __future__ import annotations

from datetime import datetime, timezone

from utils.logger import get_logger

logger = get_logger(__name__)


class SensorHealthMonitor:
    """Monitors sensor health per session."""

    def __init__(self) -> None:
        self._last_seen: dict[str, datetime] = {}
        self._dropout_count: dict[str, int] = {}

    def record_reading(self, session_id: str) -> None:
        self._last_seen[session_id] = datetime.now(timezone.utc)

    def record_dropout(self, session_id: str) -> None:
        self._dropout_count[session_id] = self._dropout_count.get(session_id, 0) + 1

    def seconds_since_last(self, session_id: str) -> float:
        last = self._last_seen.get(session_id)
        if last is None:
            return float("inf")
        return (datetime.now(timezone.utc) - last).total_seconds()

    def is_healthy(self, session_id: str, timeout_s: float = 30.0) -> bool:
        return self.seconds_since_last(session_id) < timeout_s


class FallbackInferenceStrategy:
    """Falls back to text-only inference when biometrics are unavailable."""

    def should_fallback(self, sensor_health: SensorHealthMonitor, session_id: str) -> bool:
        return not sensor_health.is_healthy(session_id)


class SignalDropoutHandler:
    """Handles signal dropout events."""

    def __init__(self) -> None:
        self._consecutive_dropouts: dict[str, int] = {}

    def record_dropout(self, session_id: str) -> int:
        self._consecutive_dropouts[session_id] = self._consecutive_dropouts.get(session_id, 0) + 1
        return self._consecutive_dropouts[session_id]

    def record_recovery(self, session_id: str) -> None:
        self._consecutive_dropouts[session_id] = 0


class ConfidenceDecayModel:
    """Decays confidence over time when sensors are unavailable."""

    def compute_decay(self, seconds_since_last_reading: float) -> float:
        """Returns confidence multiplier (1.0 = fresh, 0.0 = stale)."""
        if seconds_since_last_reading <= 5:
            return 1.0
        if seconds_since_last_reading <= 30:
            return 0.8
        if seconds_since_last_reading <= 60:
            return 0.5
        return 0.2


class DegradedModeManager:
    """Manages graceful degradation when sensors fail."""

    def __init__(self) -> None:
        self.sensor_health = SensorHealthMonitor()
        self.fallback = FallbackInferenceStrategy()
        self.dropout_handler = SignalDropoutHandler()
        self.confidence_decay = ConfidenceDecayModel()

    def get_degradation_status(self, session_id: str) -> dict:
        healthy = self.sensor_health.is_healthy(session_id)
        seconds = self.sensor_health.seconds_since_last(session_id)
        return {
            "is_degraded": not healthy,
            "seconds_since_sensor": round(seconds, 1),
            "confidence_multiplier": self.confidence_decay.compute_decay(seconds),
            "using_fallback": self.fallback.should_fallback(self.sensor_health, session_id),
        }
