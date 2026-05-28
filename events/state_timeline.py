"""State timeline — queryable history of RichHumanState for analytics."""

from datetime import datetime, timezone


class StateTimeline:
    """Tracks RichHumanState history as a queryable timeline.

    Separate from TemporalStateTracker in human_state/
    because this serves analytics/debugging vs smoothing.
    """

    def __init__(self) -> None:
        self._timelines: dict[str, list[dict]] = {}

    def record(self, session_id: str, state: dict) -> None:
        """Record a state snapshot to the timeline."""
        if session_id not in self._timelines:
            self._timelines[session_id] = []
        self._timelines[session_id].append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stress": state.get("stress"),
            "fatigue": state.get("fatigue"),
            "focus": state.get("focus"),
            "cognitive_load": state.get("cognitive_load"),
            "ux_mode": state.get("ux_mode"),
            "trend": state.get("trend"),
        })

    def get_stress_trend(self, session_id: str, last_n: int = 10) -> list[float]:
        """Get recent stress values for trend analysis."""
        timeline = self._timelines.get(session_id, [])[-last_n:]
        return [t["stress"] for t in timeline if t["stress"] is not None]

    def detect_fatigue_rising(self, session_id: str) -> bool:
        """Detect if fatigue is trending upward."""
        trend = self.get_stress_trend(session_id, 5)
        if len(trend) < 3:
            return False
        return trend[-1] > trend[0] + 0.15
