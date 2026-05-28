"""Working memory — in-process short-term buffer for current session."""

from datetime import datetime, timezone


class WorkingMemory:
    """Short-term in-process memory. No database. Pure Python list.

    Holds last N message summaries for immediate LLM context.
    Cleared when session ends.
    """

    MAX_ITEMS = 8

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self._buffer: list[dict] = []

    def add(
        self, message: str, response: str, human_state: dict, importance: float
    ) -> None:
        """Add an exchange to working memory."""
        entry = {
            "message_preview": message[:120],
            "response_preview": response[:120],
            "ux_mode": human_state.get("ux_mode"),
            "stress": round(human_state.get("stress", 0), 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "importance": round(importance, 2),
        }
        self._buffer.append(entry)
        if len(self._buffer) > self.MAX_ITEMS:
            self._buffer.pop(0)

    def get_context_strings(self, n: int = 4) -> list[str]:
        """Return last N entries as LLM-ready strings."""
        recent = self._buffer[-n:]
        return [
            f"[{e['timestamp'][:16]}] "
            f"User({e['ux_mode']}, stress={e['stress']}): "
            f"{e['message_preview']}"
            for e in recent
        ]

    def get_state_history(self) -> list[dict]:
        """Return full buffer as list of dicts."""
        return list(self._buffer)

    def clear(self) -> None:
        self._buffer.clear()

    def __len__(self) -> int:
        return len(self._buffer)
