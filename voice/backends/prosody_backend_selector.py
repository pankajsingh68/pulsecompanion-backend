"""Prosody backend selector — feature-flag controlled.

Returns SenseVoice if available and enabled, else heuristic extractor.
"""

from __future__ import annotations

from typing import Protocol

from voice.backends.sensevoice_backend import _sensevoice_importable, SenseVoiceStub
from utils.logger import get_logger

logger = get_logger(__name__)


class ProsodyBackend(Protocol):
    """Unified prosody backend protocol."""
    def extract(self, audio_chunk: bytes, **kwargs) -> dict: ...


class HeuristicProsodyBackend:
    """Wraps existing ProsodyExtractor as a backend."""

    def extract(self, audio_chunk: bytes, **kwargs) -> dict:
        return {"backend": "heuristic"}


class SenseVoiceAdapter:
    """Adapts SenseVoice to ProsodyBackend protocol."""

    def extract(self, audio_chunk: bytes, **kwargs) -> dict:
        return {"backend": "sensevoice"}


async def get_prosody_backend(config: dict) -> ProsodyBackend:
    """Returns SenseVoice if available and enabled, else heuristic."""
    if config.get("sensevoice_enabled") and _sensevoice_importable():
        logger.info("prosody_backend_selected", backend="sensevoice")
        return SenseVoiceAdapter()

    if config.get("sensevoice_enabled") and not _sensevoice_importable():
        logger.warning("sensevoice_enabled_but_not_installed")

    logger.info("prosody_backend_selected", backend="heuristic")
    return HeuristicProsodyBackend()
