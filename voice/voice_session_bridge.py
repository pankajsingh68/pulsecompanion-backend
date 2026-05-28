"""Voice Session Bridge — connects WebSocket audio to voice pipeline.

Bridges WebSocket binary audio messages to run_voice_session().
Handles backpressure, session lifecycle, and snapshot persistence.
"""

from __future__ import annotations

import asyncio
import json
import time as _time
from dataclasses import dataclass
from typing import AsyncIterator

from fastapi import WebSocket, WebSocketDisconnect

from utils.logger import get_logger

logger = get_logger(__name__)

AUDIO_QUEUE_MAX = 50


@dataclass
class SessionConfig:
    """Configuration for a voice session."""
    max_queue_size: int = AUDIO_QUEUE_MAX
    # tts_backend and llm_backend injected via
    # VoiceSessionBridge.__init__, not here


class VoiceSessionBridge:
    """Bridges WebSocket audio messages to run_voice_session().

    Handles:
    - Audio queue with backpressure (drop oldest on overflow)
    - Session snapshot load/save
    - Graceful disconnect and task cancellation
    """

    def __init__(
        self,
        tts_backend=None,
        llm_backend=None,
        degraded: bool = False,
    ) -> None:
        self._active_sessions: dict[str, asyncio.Task] = {}
        self._tts_backend = tts_backend
        self._llm_backend = llm_backend
        self._degraded = degraded

    async def handle_session(
        self,
        websocket: WebSocket,
        session_id: str,
        config: SessionConfig | None = None,
    ) -> None:
        """Full voice session lifecycle over WebSocket.

        1. Accept WebSocket
        2. Load previous snapshot if exists
        3. Start voice pipeline as background task
        4. Bridge audio bytes from WS → pipeline
        5. Bridge VoiceOutputEvents from pipeline → WS
        6. On disconnect: cancel, save snapshot
        """
        config = config or SessionConfig()
        await websocket.accept()
        session_start_time = _time.monotonic()

        logger.info("voice_session_started", session_id=session_id)

        # Audio queue with backpressure
        audio_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=config.max_queue_size)

        # Load previous session snapshot
        from voice.session_persistence import VoiceSessionPersistence
        persistence = VoiceSessionPersistence()
        prev_snapshot = await persistence.load_last_snapshot(session_id)
        if prev_snapshot:
            logger.info("voice_session_warm_start", session_id=session_id)

        # Create async audio iterator from queue
        async def audio_stream() -> AsyncIterator[bytes]:
            while True:
                try:
                    chunk = await audio_queue.get()
                    if chunk is None:  # sentinel for shutdown
                        return
                    yield chunk
                except asyncio.CancelledError:
                    return

        # Start voice pipeline task
        from voice.voice_pipeline import run_voice_session

        voice_task: asyncio.Task | None = None
        output_events: asyncio.Queue = asyncio.Queue(maxsize=100)

        # Shared state — updated during pipeline run
        session_state = {
            "cycle_count": 0,
            "overload_events": 0,
            "last_lineage_id": "",
            "recovery_achieved": False,
        }

        async def _run_pipeline():
            logger.info(
                "pipeline_backends",
                has_tts=self._tts_backend is not None,
                has_llm=self._llm_backend is not None,
            )
            try:
                async for event in run_voice_session(
                    session_id=session_id,
                    audio_input_stream=audio_stream(),
                    tts_backend=self._tts_backend,
                    llm_backend=self._llm_backend,
                    degraded=self._degraded,
                ):
                    await output_events.put(event)
                    # Track session progress
                    session_state["cycle_count"] += 1
                    if hasattr(event, "lineage_id") and event.lineage_id:
                        session_state["last_lineage_id"] = str(event.lineage_id)
                    if event.event_type == "voice.complete":
                        session_state["cycle_count"] += 1
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(
                    "voice_pipeline_error",
                    session_id=session_id,
                    error=str(e),
                )

        voice_task = asyncio.create_task(_run_pipeline())
        self._active_sessions[session_id] = voice_task

        # Output sender task
        async def _send_outputs():
            try:
                while True:
                    event = await output_events.get()
                    try:
                        payload = {
                            "event_type": event.event_type,
                            "lineage_id": str(event.lineage_id),
                            "session_id": event.session_id,
                            "chunk_index": event.chunk_index,
                            "is_final": event.is_final,
                            "timestamp": event.monotonic_timestamp,
                            "modulation": {
                                "speaking_rate": event.modulation_applied.speaking_rate,
                                "softness_level": event.modulation_applied.softness_level,
                                "response_timing_mode": event.modulation_applied.response_timing_mode,
                                "max_response_sentences": event.modulation_applied.max_response_sentences,
                            },
                        }
                        await websocket.send_json(payload)
                    except Exception:
                        break
            except asyncio.CancelledError:
                pass

        sender_task = asyncio.create_task(_send_outputs())

        # Main receive loop
        try:
            while True:
                message = await websocket.receive()

                if message.get("type") == "websocket.disconnect":
                    break

                # Binary audio data
                if "bytes" in message and message["bytes"]:
                    if audio_queue.full():
                        try:
                            audio_queue.get_nowait()  # drop oldest
                        except asyncio.QueueEmpty:
                            pass
                        logger.debug("audio_backpressure", session_id=session_id)
                    await audio_queue.put(message["bytes"])

                # Text control commands
                elif "text" in message and message["text"]:
                    try:
                        cmd = json.loads(message["text"])
                        if cmd.get("type") == "end_session":
                            break
                    except (json.JSONDecodeError, TypeError):
                        pass

        except WebSocketDisconnect:
            logger.info("voice_ws_disconnected", session_id=session_id)
        except Exception as e:
            logger.error("voice_bridge_error", session_id=session_id, error=str(e))
        finally:
            # Shutdown
            await audio_queue.put(None)  # sentinel
            sender_task.cancel()
            if voice_task:
                voice_task.cancel()
                try:
                    await voice_task
                except (asyncio.CancelledError, Exception):
                    pass

            self._active_sessions.pop(session_id, None)

            # Save session snapshot with real tracked data
            try:
                from voice.session_persistence import VoiceSessionSnapshot
                snapshot = VoiceSessionSnapshot(
                    session_id=session_id,
                    lineage_id=session_state["last_lineage_id"],
                    final_emotional_state={},    # populated in Phase 9
                    final_rhythm_state={},       # populated in Phase 9
                    final_regulation_state={},   # populated in Phase 9
                    final_pattern_state={},      # populated in Phase 9
                    session_duration=_time.monotonic() - session_start_time,
                    cycle_count=session_state["cycle_count"],
                    overload_events=session_state["overload_events"],
                    recovery_achieved=session_state["recovery_achieved"],
                    snapshot_timestamp=_time.monotonic(),
                    schema_version=1,
                )
                await persistence.save_snapshot(snapshot)
            except Exception as e:
                logger.warning("snapshot_save_failed", error=str(e))

            logger.info("voice_session_ended", session_id=session_id)

    @property
    def active_session_count(self) -> int:
        return len(self._active_sessions)
