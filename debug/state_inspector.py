"""State inspector — point-in-time and range queries over session history."""

from __future__ import annotations

from datetime import datetime, timezone

from debug.debug_models import InspectionReport


class StateInspector:
    """Point-in-time and range queries over session history."""

    def inspect_session(self, session_id: str) -> InspectionReport:
        """Generate an inspection report for a session.

        Note: In full implementation, this would query StrategyStore
        and EventStore. Currently returns a skeleton report.
        """
        return InspectionReport(
            session_id=session_id,
            generated_at=datetime.now(timezone.utc),
        )

    def get_state_at(
        self, session_id: str, timestamp: datetime
    ) -> dict | None:
        """Get state snapshot at a specific timestamp (stub)."""
        return None

    def get_strategy_at(
        self, session_id: str, timestamp: datetime
    ) -> dict | None:
        """Get strategy at a specific timestamp (stub)."""
        return None
