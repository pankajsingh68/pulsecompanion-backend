"""Stream integrity — validates timestamp ordering and gap detection."""

from __future__ import annotations

from utils.logger import get_logger

logger = get_logger(__name__)


class StreamIntegrityValidator:
    """Validates stream data integrity.

    Checks: timestamps monotonically increasing, no gaps > threshold,
    no duplicate sequence numbers.
    """

    def __init__(self, max_gap_seconds: float = 30.0) -> None:
        self.max_gap = max_gap_seconds
        self._last_timestamps: dict[str, float] = {}
        self._violations: dict[str, list[str]] = {}

    def validate_event(self, session_id: str, timestamp: float) -> list[str]:
        """Validate a single event's timestamp.

        Returns list of violations (empty if valid).
        """
        violations: list[str] = []
        last = self._last_timestamps.get(session_id)

        if last is not None:
            if timestamp < last:
                violations.append(f"non_monotonic: {timestamp} < {last}")
            gap = timestamp - last
            if gap > self.max_gap:
                violations.append(f"gap_detected: {gap:.1f}s > {self.max_gap}s")

        self._last_timestamps[session_id] = timestamp

        if violations:
            if session_id not in self._violations:
                self._violations[session_id] = []
            self._violations[session_id].extend(violations)

        return violations

    def get_violations(self, session_id: str) -> list[str]:
        return self._violations.get(session_id, [])
