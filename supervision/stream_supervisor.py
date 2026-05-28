"""Stream supervisor — monitors task liveness and stream health.

Monitors: task liveness, heartbeat freshness, stalled ingestion, stream latency.
"""

from __future__ import annotations

import asyncio

from utils.logger import get_logger

logger = get_logger(__name__)


class StreamSupervisor:
    """Monitors task liveness, heartbeat freshness, stalled ingestion, stream latency."""

    async def supervise(self, task: asyncio.Task, session_id: str) -> None:
        """Monitor a stream task for liveness."""
        # Phase 5: implement full supervision with restart logic
        logger.debug("supervision_stub", session_id=session_id)

    async def check_heartbeat(self, session_id: str) -> bool:
        """Check if a session's stream is still alive."""
        # Phase 5: check last event timestamp vs timeout
        return True
