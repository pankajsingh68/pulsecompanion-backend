"""Signal Normalizer — bridges ProsodySignal to EmotionalSignal + RhythmSignal.

The ONLY place where prosody maps to fusion input. Deterministic mapping.
"""

from __future__ import annotations

from voice.prosody_extractor import ProsodySignal
from emotion.emotional_fusion_engine import EmotionalSignal
from emotion.conversational_rhythm_engine import RhythmSignal


# Mapping table — prosody → emotional dimensions
# pacing_pressure → stress (weighted 0.6)
# hesitation_index → cognitive_load (weighted 0.7)
# speech_instability → emotional_openness (inverted, weighted 0.5)
# urgency_level → stress (weighted 0.4)
# strain_index → cognitive_load (weighted 0.3)
# silence_comfort → feeds RhythmSignal directly


async def normalize_prosody_to_signal(
    prosody: ProsodySignal,
    degraded: bool = False,
) -> tuple[EmotionalSignal, RhythmSignal]:
    """Convert ProsodySignal to EmotionalSignal + RhythmSignal.

    Deterministic. No wall-clock. No randomness.
    """
    # Map to emotional dimensions
    stress = min(1.0, prosody.pacing_pressure * 0.6 + prosody.urgency_level * 0.4)
    cognitive_load = min(1.0, prosody.hesitation_index * 0.7 + prosody.strain_index * 0.3)
    emotional_openness = max(0.0, 1.0 - prosody.speech_instability * 0.5)
    engagement = min(1.0, prosody.urgency_level * 0.4 + (1.0 - prosody.silence_comfort) * 0.3 + 0.3)

    confidence = prosody.extraction_confidence
    if degraded:
        confidence = min(confidence, 0.4)

    emotional_signal = EmotionalSignal(
        source="voice",
        confidence=confidence,
        timestamp=prosody.monotonic_timestamp,
        values={
            "stress": round(stress, 6),
            "cognitive_load": round(cognitive_load, 6),
            "emotional_openness": round(emotional_openness, 6),
            "engagement": round(engagement, 6),
        },
    )

    rhythm_signal = RhythmSignal(
        pause_duration=prosody.silence_comfort * 2.0,
        interruption_frequency=prosody.pacing_pressure * 0.5,
        speech_pacing=1.0 - prosody.pacing_pressure,
        silence_comfort=prosody.silence_comfort,
        response_latency=prosody.hesitation_index * 0.6,
        conversational_volatility=prosody.speech_instability,
        timestamp=prosody.monotonic_timestamp,
    )

    return emotional_signal, rhythm_signal
