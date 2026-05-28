"""Dead connection detection and cleanup via periodic heartbeat checks."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from utils.logger import get_logger

if TYPE_CHECKING:
    from websocket.manager import ConnectionManager

logger = get_logger(__name__)


class HeartbeatMonitor:
    """Periodically checks for idle WebSocket connections and cleans them up.

    Args:
        manager: The ConnectionManager instance to monitor.
        interval_seconds: How often to run the check (default 30s).
        timeout_seconds: Max idle time before a connection is considered dead (default 90s).
    """

    def __init__(
        self,
        manager: "ConnectionManager",
        interval_seconds: int = 30,
        timeout_seconds: int = 90,
    ):
        self.manager = manager
        self.interval = interval_seconds
        self.timeout = timeout_seconds
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the background heartbeat check task."""
        self._task = asyncio.create_task(self._run())
        logger.info("heartbeat_started", interval=self.interval)

    async def stop(self) -> None:
        """Cancel the background heartbeat task."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("heartbeat_stopped")

    async def _run(self) -> None:
        """Main loop: sleep then check connections."""
        try:
            while True:
                await asyncio.sleep(self.interval)
                await self._check_all_connections()
        except asyncio.CancelledError:
            return

    async def _check_all_connections(self) -> None:
        """Identify and disconnect idle sessions exceeding the timeout."""
        now = datetime.now(timezone.utc)
        dead_sessions: list[str] = []

        for session_id in self.manager.get_active_sessions():
            meta = self.manager.get_session_metadata(session_id)
            if meta is None:
                continue

            last_seen = meta.get("last_seen", meta.get("connected_at"))
            if last_seen is None:
                continue

            seconds_idle = (now - last_seen).total_seconds()
            if seconds_idle > self.timeout:
                dead_sessions.append(session_id)
                logger.warning(
                    "ws_connection_timeout",
                    session_id=session_id,
                    idle_seconds=round(seconds_idle),
                )

        for session_id in dead_sessions:
            await self.manager.disconnect(session_id)
            logger.info("ws_dead_connection_cleaned", session_id=session_id)

        if dead_sessions:
            logger.info("heartbeat_cleanup_done", removed=len(dead_sessions))
