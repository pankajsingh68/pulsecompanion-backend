"""Pydantic validation schemas for incoming WebSocket messages."""

import json
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class BaseWSMessage(BaseModel):
    """Base schema for all incoming WebSocket messages."""

    type: str
    session_id: str | None = None
    timestamp: datetime | None = None

    model_config = ConfigDict(extra="allow")


class PingMessage(BaseWSMessage):
    """Heartbeat ping from client."""

    type: Literal["ping"]


class EchoMessage(BaseWSMessage):
    """Echo request for connection testing."""

    type: Literal["echo"]
    message: str


class ChatMessage(BaseWSMessage):
    """Chat message to be processed by the LLM pipeline."""

    type: Literal["chat"]
    message: str = Field(..., min_length=1, max_length=4000)
    biometric_hint: dict | None = None


class InterruptMessage(BaseWSMessage):
    """Client signals: stop current LLM generation."""

    type: Literal["interrupt"]


class TypingMessage(BaseWSMessage):
    """Typing indicator from client."""

    type: Literal["typing"]
    is_typing: bool


class VoiceChunkMessage(BaseWSMessage):
    """Audio chunk from client voice input (placeholder)."""

    type: Literal["voice_chunk"]
    chunk_index: int
    audio_b64: str
    is_final: bool = False


class EmotionUpdateMessage(BaseWSMessage):
    """Biometric/emotion data from wearable or camera (placeholder)."""

    type: Literal["emotion_update"]
    source: str  # "wearable" | "camera" | "manual"
    hr: float | None = None
    hrv: float | None = None
    gsr: float | None = None


# Type dispatch map
_TYPE_MAP: dict[str, type[BaseWSMessage]] = {
    "ping": PingMessage,
    "echo": EchoMessage,
    "chat": ChatMessage,
    "interrupt": InterruptMessage,
    "typing": TypingMessage,
    "voice_chunk": VoiceChunkMessage,
    "emotion_update": EmotionUpdateMessage,
}


def parse_ws_message(raw: str) -> BaseWSMessage | None:
    """Safely parse a raw websocket string into a typed message.

    Returns None only if the input is completely unparseable.
    Tries JSON first. Falls back to treating as a plain echo string.

    Args:
        raw: Raw text received from the WebSocket.

    Returns:
        A validated message model, or an EchoMessage fallback for plain strings.
    """
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            # JSON but not an object — treat as echo
            return EchoMessage(type="echo", message=raw[:500])

        msg_type = data.get("type", "echo")
        model = _TYPE_MAP.get(msg_type, BaseWSMessage)
        return model.model_validate(data)
    except (json.JSONDecodeError, ValidationError, Exception):
        # Plain string fallback → treat as echo
        return EchoMessage(type="echo", message=raw[:500])
