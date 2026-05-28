"""Per-session baseline storage."""

from __future__ import annotations

from typing import TYPE_CHECKING

from baseline.adaptive_thresholds import AdaptiveThresholds

if TYPE_CHECKING:
    from sensors.models import BiometricSnapshot


class BaselineStore:
    """Manages one AdaptiveThresholds per session.

    Designed to be future-compatible with Redis.
    """

    def __init__(self) -> None:
        self._baselines: dict[str, AdaptiveThresholds] = {}

    def get_or_create(self, session_id: str) -> AdaptiveThresholds:
        """Get or create adaptive thresholds for a session."""
        if session_id not in self._baselines:
            self._baselines[session_id] = AdaptiveThresholds(session_id)
        return self._baselines[session_id]

    def update_from_snapshot(
        self, session_id: str, snapshot: "BiometricSnapshot"
    ) -> None:
        """Update session baseline from a biometric snapshot."""
        thresholds = self.get_or_create(session_id)
        thresholds.update(snapshot)
