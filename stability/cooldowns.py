"""Cooldown manager — enforces minimum hold times per field."""

from datetime import datetime, timezone


class CooldownManager:
    """Enforces minimum hold times per-session per-field.

    Fields with cooldowns: ux_mode, suggest_break, response_tone.
    """

    def __init__(self) -> None:
        self._last_changes: dict[str, dict[str, datetime]] = {}

    def is_on_cooldown(
        self, session_id: str, field: str, cooldown_seconds: float
    ) -> bool:
        """Check if a field is still on cooldown."""
        session_changes = self._last_changes.get(session_id, {})
        last = session_changes.get(field)
        if last is None:
            return False
        elapsed = (datetime.now(timezone.utc) - last).total_seconds()
        return elapsed < cooldown_seconds

    def mark_changed(self, session_id: str, field: str) -> None:
        """Mark that a field just changed."""
        if session_id not in self._last_changes:
            self._last_changes[session_id] = {}
        self._last_changes[session_id][field] = datetime.now(timezone.utc)
