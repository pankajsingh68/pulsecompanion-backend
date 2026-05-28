"""WebSocket connection lifecycle and message routing."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from fastapi import WebSocket, WebSocketDisconnect

from utils.logger import get_logger
from websocket.handlers import (
    handle_chat,
    handle_echo,
    handle_emotion_update,
    handle_interrupt,
    handle_ping,
    handle_typing,
    handle_unknown,
    handle_voice_chunk,
)
from websocket.schemas import parse_ws_message

if TYPE_CHECKING:
    from websocket.manager import ConnectionManager

logger = get_logger(__name__)


async def handle_connection(
    websocket: WebSocket, session_id: str, manager: "ConnectionManager"
) -> None:
    """Full WebSocket session lifecycle.

    1. Connect
    2. Send welcome event
    3. Enter receive loop
    4. Gracefully handle disconnect

    Args:
        websocket: The incoming WebSocket connection.
        session_id: Unique session identifier from the URL path.
        manager: The shared ConnectionManager instance.
    """
    is_new = not manager.is_connected(session_id)
    await manager.connect(session_id, websocket)

    # Send welcome immediately after connection
    await manager.send_json(session_id, {
        "type": "connected",
        "session_id": session_id,
        "reconnect": not is_new,
        "message": "PulseCompanion adaptive AI ready",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    logger.info("ws_session_started", session_id=session_id)

    try:
        await _receive_loop(session_id, websocket, manager)
    except WebSocketDisconnect:
        logger.info("ws_client_disconnected", session_id=session_id)
    except Exception as e:
        logger.error("ws_session_error", session_id=session_id, error=str(e))
    finally:
        await manager.disconnect(session_id)
        logger.info("ws_session_ended", session_id=session_id)


async def _receive_loop(
    session_id: str, websocket: WebSocket, manager: "ConnectionManager"
) -> None:
    """Receive loop — runs until disconnect or error.

    Each iteration:
    1. Receive raw text
    2. Parse + validate via schemas
    3. Route to correct handler
    4. Never crash on bad input
    """
    while True:
        raw = await websocket.receive_text()
        receive_time = datetime.now(timezone.utc)

        logger.info(
            "ws_message_received",
            session_id=session_id,
            raw_preview=raw[:100],
        )

        message = parse_ws_message(raw)
        if message is None:
            await handle_unknown(session_id, "parse_failed", manager)
            continue

        # Route by message type
        msg_type = message.type
        logger.debug("ws_routing", session_id=session_id, type=msg_type)

        if msg_type == "ping":
            await handle_ping(session_id, message, manager)
        elif msg_type == "echo":
            await handle_echo(session_id, message, manager)
        elif msg_type == "chat":
            await handle_chat(session_id, message, manager)
        elif msg_type == "interrupt":
            await handle_interrupt(session_id, message, manager)
        elif msg_type == "typing":
            await handle_typing(session_id, message, manager)
        elif msg_type == "voice_chunk":
            await handle_voice_chunk(session_id, message, manager)
        elif msg_type == "emotion_update":
            await handle_emotion_update(session_id, message, manager)
        else:
            await handle_unknown(session_id, msg_type, manager)

        # Latency tracking
        latency_ms = (
            datetime.now(timezone.utc) - receive_time
        ).total_seconds() * 1000
        logger.debug(
            "ws_message_processed",
            session_id=session_id,
            type=msg_type,
            latency_ms=round(latency_ms, 2),
        )
