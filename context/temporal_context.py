"""Temporal context — time-based contextual hints."""

from datetime import datetime, timezone


class TemporalContext:
    """Provides time-based contextual hints.

    Avoids: flagging low engagement at 2AM as a problem.
    """

    def get_context(self) -> dict:
        """Get current temporal context."""
        now = datetime.now(timezone.utc)
        hour = now.hour
        return {
            "hour_of_day": hour,
            "is_night": hour >= 22 or hour < 6,
            "is_morning": 6 <= hour < 10,
            "is_work_hours": 9 <= hour < 18,
            "day_of_week": now.strftime("%A"),
            "is_weekend": now.weekday() >= 5,
        }

    def adjust_fatigue_expectation(
        self, base_fatigue: float, context: dict
    ) -> float:
        """Night hours: fatigue is expected, don't over-flag it."""
        if context.get("is_night"):
            return max(0.0, base_fatigue - 0.2)
        return base_fatigue
