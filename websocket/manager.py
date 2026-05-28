"""WebSocket connection manager — connection lifecycle only."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import WebSocket

from utils.logger import get_logger

logger = get_logger(__name__)


class ConnectionManager:
    """Manages WebSocket connections keyed by session_id.

    Responsibilities:
    - Accept/close connections
    - Track connection metadata (connected_at, message_count, last_seen)
    - Send JSON payloads to specific sessions or broadcast to all
    - Provide session introspection helpers

    Does NOT handle message routing or business logic.
    """

    def __init__(self) -> None:
        self.active_connections: dict[str, WebSocket] = {}
        self.connection_metadata: dict[str, dict] = {}

    async def connect(self, session_id: str, websocket: WebSocket) -> bool:
        """Accept and register a WebSocket connection.

        Args:
            session_id: Unique session identifier.
            websocket: The FastAPI WebSocket instance.

        Returns:
            True if this is a new connection, False if reconnect.
        """
        await websocket.accept()
        now = datetime.now(timezone.utc)
        is_reconnect = session_id in self.active_connections

        self.active_connections[session_id] = websocket

        if is_reconnect:
            # Update existing metadata
            meta = self.connection_metadata.get(session_id, {})
            meta["reconnect_count"] = meta.get("reconnect_count", 0) + 1
            meta["last_seen"] = now
            self.connection_metadata[session_id] = meta
            logger.info("ws_reconnected", session_id=session_id)
        else:
            # Initialize fresh metadata
            self.connection_metadata[session_id] = {
                "connected_at": now,
                "message_count": 0,
                "last_seen": now,
                "reconnect_count": 0,
            }
            logger.info("ws_connected", session_id=session_id)

        return not is_reconnect

    async def disconnect(self, session_id: str) -> None:
        """Remove a WebSocket connection from the registry.

        Metadata is preserved for analytics — only the live socket is removed.

        Args:
            session_id: Session identifier to disconnect.
        """
        self.active_connections.pop(session_id, None)

        meta = self.connection_metadata.get(session_id)
        if meta and "connected_at" in meta:
            duration = (
                datetime.now(timezone.utc) - meta["connected_at"]
            ).total_seconds()
            logger.info(
                "ws_disconnected",
                session_id=session_id,
                duration_seconds=round(duration),
            )
        else:
            logger.info("ws_disconnected", session_id=session_id)

    async def send_json(self, session_id: str, payload: dict) -> bool:
        """Send a JSON payload to a specific session.

        Args:
            session_id: Target session identifier.
            payload: Dictionary to serialize and send.

        Returns:
            True if sent successfully, False otherwise.
        """
        websocket = self.active_connections.get(session_id)
        if websocket is None:
            logger.debug("ws_send_skipped", session_id=session_id)
            return False

        try:
            await websocket.send_json(payload)

            # Update metadata
            meta = self.connection_metadata.get(session_id)
            if meta:
                meta["message_count"] = meta.get("message_count", 0) + 1
                meta["last_seen"] = datetime.now(timezone.utc)

            logger.debug(
                "ws_send_success",
                session_id=session_id,
                event_type=payload.get("type", "unknown"),
            )
            return True
        except Exception as e:
            logger.error("ws_send_failed", session_id=session_id, error=str(e))
            await self.disconnect(session_id)
            return False

    # ------------------------------------------------------------------
    # Public interface used by api/routes/chat.py — DO NOT CHANGE SIGNATURES
    # ------------------------------------------------------------------

    async def send_event(self, session_id: str, event: dict) -> None:
        """Send an event dict to a specific session's WebSocket.

        This method is used by api/routes/chat.py and must retain its signature.

        Args:
            session_id: Target session identifier.
            event: Event dictionary to send as JSON.
        """
        await self.send_json(session_id, event)

    async def broadcast_state_update(
        self, session_id: str, human_state: dict, ux_mode: str
    ) -> None:
        """Send a STATE_UPDATE event to the session's WebSocket.

        This method is used by api/routes/chat.py and must retain its signature.

        Args:
            session_id: Target session identifier.
            human_state: Current estimated human state dictionary.
            ux_mode: Current UX mode string.
        """
        from websocket.events import state_update_event

        event = state_update_event(human_state, ux_mode)
        await self.send_json(session_id, event)

    # ------------------------------------------------------------------
    # Broadcast and introspection helpers
    # ------------------------------------------------------------------

    async def broadcast_all(self, event: dict) -> dict:
        """Send an event to ALL active sessions.

        Args:
            event: Event dictionary to broadcast.

        Returns:
            Dict with "sent" and "failed" counts.
        """
        results = {"sent": 0, "failed": 0}
        for session_id in list(self.active_connections.keys()):
            success = await self.send_json(session_id, event)
            if success:
                results["sent"] += 1
            else:
                results["failed"] += 1
        return results

    def get_active_sessions(self) -> list[str]:
        """Return list of currently connected session IDs."""
        return list(self.active_connections.keys())

    def is_connected(self, session_id: str) -> bool:
        """Check if a session is currently connected."""
        return session_id in self.active_connections

    def get_session_metadata(self, session_id: str) -> dict | None:
        """Return metadata for a session, or None if not found."""
        return self.connection_metadata.get(session_id)
