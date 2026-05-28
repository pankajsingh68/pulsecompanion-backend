"""WebSocket message handlers — one function per message type."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from utils.logger import get_logger
from websocket.schemas import (
    ChatMessage,
    EchoMessage,
    EmotionUpdateMessage,
    InterruptMessage,
    PingMessage,
    TypingMessage,
    VoiceChunkMessage,
)

if TYPE_CHECKING:
    from websocket.manager import ConnectionManager

logger = get_logger(__name__)


async def handle_ping(
    session_id: str, message: PingMessage, manager: "ConnectionManager"
) -> None:
    """Respond to heartbeat pings."""
    await manager.send_json(session_id, {
        "type": "pong",
        "session_id": session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    logger.debug("ws_pong_sent", session_id=session_id)


async def handle_echo(
    session_id: str, message: EchoMessage, manager: "ConnectionManager"
) -> None:
    """Echo handler for connection testing."""
    await manager.send_json(session_id, {
        "type": "echo",
        "message": message.message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    logger.info("ws_echo_sent", session_id=session_id)


async def handle_chat(
    session_id: str, message: ChatMessage, manager: "ConnectionManager"
) -> None:
    """Phase 2 wiring point: this is where LangGraph pipeline will be called.

    For now: send acknowledgement and log.
    Future: await graph.ainvoke({...}) then stream tokens back.
    """
    await manager.send_json(session_id, {
        "type": "chat_ack",
        "status": "queued",
        "session_id": session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    logger.info(
        "ws_chat_queued",
        session_id=session_id,
        message_length=len(message.message),
    )


async def handle_interrupt(
    session_id: str, message: InterruptMessage, manager: "ConnectionManager"
) -> None:
    """Placeholder: In future phase, this will cancel the active asyncio Task
    running LLM generation for this session.

    Pattern: task_registry[session_id].cancel()
    """
    await manager.send_json(session_id, {
        "type": "interrupt_ack",
        "status": "noted",
        "session_id": session_id,
    })
    logger.info("ws_interrupt_received", session_id=session_id)


async def handle_typing(
    session_id: str, message: TypingMessage, manager: "ConnectionManager"
) -> None:
    """Log typing indicator — no response needed."""
    logger.debug(
        "ws_typing_indicator",
        session_id=session_id,
        is_typing=message.is_typing,
    )


async def handle_voice_chunk(
    session_id: str, message: VoiceChunkMessage, manager: "ConnectionManager"
) -> None:
    """Placeholder: future voice pipeline entry point."""
    logger.info(
        "ws_voice_chunk_received",
        session_id=session_id,
        chunk_index=message.chunk_index,
        is_final=message.is_final,
    )
    await manager.send_json(session_id, {
        "type": "voice_ack",
        "chunk_index": message.chunk_index,
        "status": "received",
    })


async def handle_emotion_update(
    session_id: str, message: EmotionUpdateMessage, manager: "ConnectionManager"
) -> None:
    """Placeholder: future wearable biometric input handler."""
    logger.info(
        "ws_emotion_update",
        session_id=session_id,
        source=message.source,
    )


async def handle_unknown(
    session_id: str, raw_type: str, manager: "ConnectionManager"
) -> None:
    """Handle unrecognized message types."""
    await manager.send_json(session_id, {
        "type": "error",
        "code": "UNKNOWN_MESSAGE_TYPE",
        "message": f"Unknown type: {raw_type}",
    })
    logger.warning("ws_unknown_type", session_id=session_id, type=raw_type)
