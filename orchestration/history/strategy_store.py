"""Append-only per-session strategy history."""

from __future__ import annotations

from orchestration.history.history_models import StrategySnapshot, StrategyTransition


class StrategyStore:
    """Append-only per-session strategy history.

    Max 100 entries per session (drop oldest).
    """

    def __init__(self, max_per_session: int = 100) -> None:
        self._history: dict[str, list[StrategySnapshot]] = {}
        self.max_per_session = max_per_session

    def append(self, session_id: str, snapshot: StrategySnapshot) -> None:
        """Append a strategy snapshot to session history."""
        if session_id not in self._history:
            self._history[session_id] = []
        self._history[session_id].append(snapshot)
        if len(self._history[session_id]) > self.max_per_session:
            self._history[session_id].pop(0)

    def get_history(self, session_id: str) -> list[StrategySnapshot]:
        """Get full history for a session."""
        return self._history.get(session_id, [])

    def get_latest(self, session_id: str) -> StrategySnapshot | None:
        """Get the most recent snapshot."""
        history = self._history.get(session_id, [])
        return history[-1] if history else None

    def get_transitions(self, session_id: str) -> list[StrategyTransition]:
        """Get all transitions for a session."""
        return [s.transition for s in self.get_history(session_id)]
