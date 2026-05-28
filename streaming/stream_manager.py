"""Stream manager — manages continuous biometric streams per session."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from sensors.mock_stream import MockBiometricStream
from utils.logger import get_logger

if TYPE_CHECKING:
    from streaming.ingestion import SensorIngestionPipeline

logger = get_logger(__name__)


class StreamManager:
    """Manages continuous biometric streams per session.

    Runs MockBiometricStream as asyncio background task during demo.
    Future: manages Galaxy Watch WebSocket connections.
    """

    def __init__(self, ingestion_pipeline: "SensorIngestionPipeline") -> None:
        self.pipeline = ingestion_pipeline
        self._tasks: dict[str, asyncio.Task] = {}
        self._streams: dict[str, MockBiometricStream] = {}

    async def start_mock_stream(
        self, session_id: str, interval_seconds: float = 5.0
    ) -> None:
        """Start simulated biometric stream for demo.

        Args:
            session_id: The session to stream to.
            interval_seconds: Time between readings.
        """
        if session_id in self._tasks:
            return  # already streaming

        stream = MockBiometricStream(session_id)
        self._streams[session_id] = stream
        task = asyncio.create_task(
            self._stream_loop(session_id, stream, interval_seconds)
        )
        self._tasks[session_id] = task
        logger.info(
            "mock_stream_started",
            session_id=session_id,
            interval=interval_seconds,
        )

    async def stop_stream(self, session_id: str) -> None:
        """Stop a running stream for a session."""
        task = self._tasks.pop(session_id, None)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._streams.pop(session_id, None)
        logger.info("stream_stopped", session_id=session_id)

    async def _stream_loop(
        self,
        session_id: str,
        stream: MockBiometricStream,
        interval: float,
    ) -> None:
        """Background loop that continuously ingests sensor data."""
        try:
            while True:
                snapshot = await stream.next_snapshot()
                await self.pipeline.ingest(session_id, snapshot)
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            return
        except Exception as e:
            logger.error(
                "stream_error", session_id=session_id, error=str(e)
            )
