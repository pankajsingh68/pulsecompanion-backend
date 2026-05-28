"""Data models for the Human State Engine."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field


class RichHumanState(BaseModel):
    """Extended human state with all Phase 2 dimensions.

    Preserves backward-compatible fields (stress, focus, fatigue, confidence,
    ux_mode, timestamp) while adding new cognitive/emotional dimensions.
    """

    # --- EXISTING FIELDS (keep exact names, used by rest of backend) ---
    stress: float = Field(default=0.2, ge=0.0, le=1.0)
    focus: float = Field(default=0.5, ge=0.0, le=1.0)
    fatigue: float = Field(default=0.2, ge=0.0, le=1.0)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    ux_mode: str = "normal"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # --- NEW DIMENSIONS (Phase 2 additions) ---
    cognitive_load: float = Field(default=0.5, ge=0.0, le=1.0)
    engagement: float = Field(default=0.5, ge=0.0, le=1.0)
    emotional_stability: float = Field(default=0.7, ge=0.0, le=1.0)
    social_energy: float = Field(default=0.5, ge=0.0, le=1.0)
    receptiveness: float = Field(default=0.6, ge=0.0, le=1.0)
    recovery_need: float = Field(default=0.2, ge=0.0, le=1.0)

    # --- SIGNAL QUALITY METADATA ---
    signal_sources: list[str] = []
    inference_confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    # --- TEMPORAL METADATA ---
    state_age_seconds: float = 0.0
    trend: str = "stable"

    # --- RUNTIME LINEAGE (minted at ingestion, forwarded unchanged) ---
    lineage_id: str | None = None
    created_monotonic: float | None = None
    event_timestamp: datetime | None = None

    model_config = ConfigDict(extra="allow")

    def to_legacy_human_state(self) -> dict:
        """Returns dict compatible with existing models/human_state.py fields.

        Used by graph nodes and websocket events that expect the old format.
        """
        return {
            "stress": self.stress,
            "focus": self.focus,
            "fatigue": self.fatigue,
            "confidence": self.confidence,
            "ux_mode": self.ux_mode,
            "timestamp": self.timestamp.isoformat(),
        }


class RawSignals(BaseModel):
    """Container for all raw inputs before processing."""

    # Text signals
    message: str = ""
    message_length: int = 0
    message_word_count: int = 0

    # Biometric signals (from wearable or biometric_hint)
    hr: float | None = None
    hrv: float | None = None
    gsr: float | None = None

    # Behavioral signals
    typing_duration_ms: float | None = None
    session_message_count: int = 0
    time_since_last_message_s: float | None = None

    # Voice signals (future)
    voice_energy: float | None = None
    speech_rate: float | None = None

    # Context
    session_id: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SignalScores(BaseModel):
    """Normalized 0-1 scores from each signal processor."""

    # Each score is None if that signal was unavailable
    text_stress: float | None = None
    text_focus: float | None = None
    text_fatigue: float | None = None
    text_engagement: float | None = None

    bio_stress: float | None = None
    bio_fatigue: float | None = None
    bio_stability: float | None = None

    behavior_cognitive_load: float | None = None
    behavior_engagement: float | None = None

    contributing_sources: list[str] = []
