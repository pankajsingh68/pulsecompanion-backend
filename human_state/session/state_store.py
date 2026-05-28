"""Per-session state isolation and management."""

from __future__ import annotations

from human_state.models import RichHumanState
from human_state.temporal.tracker import TemporalStateTracker
from utils.logger import get_logger

logger = get_logger(__name__)


class SessionStateStore:
    """Manages one TemporalStateTracker per session.

    Designed to be future-compatible with Redis
    (swap dict for Redis hash when scaling).
    """

    def __init__(self) -> None:
        self._sessions: dict[str, TemporalStateTracker] = {}

    def get_or_create_tracker(self, session_id: str) -> TemporalStateTracker:
        """Get existing tracker or create a new one for the session."""
        if session_id not in self._sessions:
            self._sessions[session_id] = TemporalStateTracker()
            logger.info("session_state_created", session_id=session_id)
        return self._sessions[session_id]

    def update_state(
        self, session_id: str, raw_state: RichHumanState
    ) -> RichHumanState:
        """Update session state with a new raw state, applying smoothing.

        Args:
            session_id: The session to update.
            raw_state: Unsmoothed state from fusion.

        Returns:
            Smoothed RichHumanState.
        """
        tracker = self.get_or_create_tracker(session_id)
        smoothed = tracker.update(raw_state)
        logger.debug(
            "session_state_updated",
            session_id=session_id,
            stress=round(smoothed.stress, 3),
            ux_mode=smoothed.ux_mode,
            trend=smoothed.trend,
        )
        return smoothed

    def get_current_state(self, session_id: str) -> RichHumanState | None:
        """Get the current smoothed state for a session, or None."""
        tracker = self._sessions.get(session_id)
        if tracker is None:
            return None
        return tracker._smoothed

    def get_session_summary(self, session_id: str) -> dict:
        """Get a summary of the session's state history."""
        tracker = self._sessions.get(session_id)
        if tracker is None:
            return {}
        return {
            "session_id": session_id,
            "message_count": len(tracker._history),
            "averages": tracker.get_session_averages(),
            "current_trend": (
                tracker._smoothed.trend if tracker._smoothed else "unknown"
            ),
        }

    def cleanup_session(self, session_id: str) -> None:
        """Remove a session's state tracker."""
        self._sessions.pop(session_id, None)
        logger.info("session_state_cleaned", session_id=session_id)
