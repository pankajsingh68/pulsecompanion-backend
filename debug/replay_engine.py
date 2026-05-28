"""Replay engine — replays session event history deterministically.

Useful for: debugging, UX auditing, future ML dataset generation.
"""

from __future__ import annotations

from datetime import datetime

from debug.debug_models import ReplayFrame


class ReplayEngine:
    """Replays a session's event history deterministically."""

    async def replay_session(
        self,
        session_id: str,
        up_to: datetime | None = None,
        speed_multiplier: float = 10.0,
    ) -> list[ReplayFrame]:
        """Replay a session's events (stub implementation).

        Args:
            session_id: Session to replay.
            up_to: Optional timestamp to replay up to.
            speed_multiplier: Playback speed.

        Returns:
            List of ReplayFrames (empty in stub).
        """
        # Phase 7: implement full replay from EventStore
        return []
