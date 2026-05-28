"""Voice Pipeline — single entry point for Phase 6 voice runtime.

Wires VAD → Transcription → Prosody → Fusion → Modulation → TTS → Turn-taking.
No module outside voice/ is modified.
"""

from __future__ import annotations

import asyncio
from typing import AsyncIterator
from uuid import UUID

from voice.vad_runtime import VADRuntime, VADBackend
from voice.transcription_stream import TranscriptionStream, TranscriptionBackend
from voice.prosody_extractor import ProsodyExtractor
from voice.signal_normalizer import normalize_prosody_to_signal
from voice.response_modulator import ResponseModulator, VoiceModulation
from voice.voice_output_stream import VoiceOutputStream, VoiceOutputEvent, TTSBackend
from voice.conversational_runtime import ConversationalRuntime
from emotion.emotional_intelligence_core import EmotionalIntelligenceCore
from utils.logger import get_logger

logger = get_logger(__name__)


async def run_voice_session(
    session_id: str,
    audio_input_stream: AsyncIterator[bytes],
    tts_backend: TTSBackend | None = None,
    transcription_backend: TranscriptionBackend | None = None,
    vad_backend: VADBackend | None = None,
    degraded: bool = False,
    bus=None,
) -> AsyncIterator[VoiceOutputEvent]:
    """Run a complete voice session.

    Single entry point. Everything inside voice/ is internal.
    Error handling: if any stage raises, emit pipeline.degraded, continue.
    """
    # Initialize all components
    vad = VADRuntime(session_id, backend=vad_backend, bus=bus)
    transcription = TranscriptionStream(session_id, backend=transcription_backend, bus=bus)
    prosody = ProsodyExtractor(session_id)
    modulator = ResponseModulator()
    output_stream = VoiceOutputStream(session_id, backend=tts_backend, bus=bus)
    conversation = ConversationalRuntime(session_id)
    ei_core = EmotionalIntelligenceCore()

    timestamp = 0.0
    current_lineage: UUID | None = None

    try:
        async for audio_chunk in audio_input_stream:
            timestamp += 0.1  # monotonic increment per chunk

            # VAD processing
            try:
                vad_event = await vad.process_chunk(audio_chunk, timestamp)
            except Exception as e:
                logger.warning("vad_error", error=str(e))
                continue

            if vad_event:
                if vad_event.event_type == "vad.speech_start":
                    current_lineage = vad_event.lineage_id
                    conversation.user_started_speaking(timestamp)
                    # Interrupt system output if speaking
                    output_stream.interrupt()

                elif vad_event.event_type == "vad.speech_end" and current_lineage:
                    conversation.user_stopped_speaking(timestamp)

                    # Finalize transcription
                    try:
                        tx_event = await transcription.finalize_segment(
                            current_lineage, timestamp
                        )
                    except Exception:
                        tx_event = None

                    # Extract prosody
                    try:
                        prosody_signal = prosody.extract(
                            audio_chunk, current_lineage, timestamp,
                            silence_duration=vad_event.silence_duration,
                        )
                    except Exception:
                        prosody_signal = prosody.extract(b"", current_lineage, timestamp)

                    # Normalize to fusion input
                    try:
                        emotional_signal, rhythm_signal = await normalize_prosody_to_signal(
                            prosody_signal, degraded=degraded
                        )
                    except Exception:
                        continue

                    # Run emotional intelligence cycle
                    try:
                        cycle_output = await ei_core.run_cycle(
                            [emotional_signal], rhythm_signal, degraded=degraded
                        )
                    except Exception as e:
                        logger.warning("ei_cycle_error", error=str(e))
                        continue

                    # Check if system should speak
                    should_speak = conversation.should_speak(
                        cycle_output.regulation,
                        vad_event.silence_duration,
                        prosody_signal.speech_instability,
                    )

                    if not should_speak:
                        continue

                    # Compute response delay
                    delay = conversation.compute_response_delay(
                        cycle_output.rhythm_state,
                        cycle_output.regulation,
                        cycle_output.emotional_state.cognitive_load,
                        timestamp,
                    )
                    await asyncio.sleep(min(delay, 3.0))

                    # Modulate voice output
                    modulation = modulator.modulate(cycle_output.directive)

                    # Apply sentence limit from conversation pressure
                    effective_sentences = min(
                        modulation.max_response_sentences,
                        conversation.get_max_sentences(),
                    )
                    if effective_sentences != modulation.max_response_sentences:
                        modulation = VoiceModulation(
                            speaking_rate=modulation.speaking_rate,
                            pause_before_response=modulation.pause_before_response,
                            inter_sentence_pause=modulation.inter_sentence_pause,
                            softness_level=modulation.softness_level,
                            response_timing_mode=modulation.response_timing_mode,
                            allow_mid_response_pause=modulation.allow_mid_response_pause,
                            max_response_sentences=effective_sentences,
                            modulation_version=modulation.modulation_version,
                        )

                    # Generate response text (placeholder — LLM integration point)
                    response_text = "I hear you. Take your time."

                    # Stream TTS output
                    conversation.system_starts_speaking(timestamp)
                    async for voice_event in output_stream.stream_response(
                        response_text, modulation, current_lineage, timestamp
                    ):
                        yield voice_event

            # Process audio for transcription during speech
            if vad.is_speaking and current_lineage:
                try:
                    await transcription.process_audio(
                        audio_chunk, current_lineage, timestamp
                    )
                except Exception:
                    pass

    except asyncio.CancelledError:
        logger.info("voice_session_cancelled", session_id=session_id)
        raise
    except Exception as e:
        logger.error("voice_pipeline_error", session_id=session_id, error=str(e))
        if bus:
            try:
                await bus.emit("pipeline.degraded", {"session_id": session_id, "error": str(e)})
            except Exception:
                pass
