"""Voice signal extraction — PLACEHOLDER for future implementation.

Will process:
- speech rate → fatigue/stress signal
- voice energy → engagement signal
- pitch variation → emotional stability signal
- silence gaps → cognitive load signal

Integration point: websocket voice_chunk handler in
websocket/handlers.py handle_voice_chunk()
"""

from utils.logger import get_logger

logger = get_logger(__name__)


class VoiceSignalExtractor:
    """PLACEHOLDER: Future voice/audio signal processing."""

    def extract(
        self,
        voice_energy: float | None = None,
        speech_rate: float | None = None,
    ) -> dict:
        """Extract voice signals — not implemented in Phase 2.

        Returns:
            Empty dict (no voice processing yet).
        """
        logger.debug("voice_signal_extractor_placeholder_called")
        return {}
