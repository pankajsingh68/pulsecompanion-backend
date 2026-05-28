"""Pydantic models for the UX orchestration layer."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class VerbosityLevel(str, Enum):
    MINIMAL = "minimal"
    SHORT = "short"
    NORMAL = "normal"
    DETAILED = "detailed"


class ResponseTone(str, Enum):
    CALM = "calm"
    NEUTRAL = "neutral"
    TECHNICAL = "technical"
    WARM = "warm"
    ENERGETIC = "energetic"


class UXStrategy(BaseModel):
    """Full behavioral specification output by UX Orchestrator.

    Consumed by: LLM prompt injector, WebSocket events, frontend.
    """

    # Core mode (backward compat with existing prompt templates)
    ux_mode: str

    # Response behavior
    verbosity_level: VerbosityLevel
    response_tone: ResponseTone
    max_response_tokens: int

    # Interruption + notification control
    suppress_notifications: bool
    interruption_sensitivity: float = Field(ge=0.0, le=1.0)
    notification_delay_seconds: int

    # Cognitive support
    cognitive_load_reduction: bool
    suggest_break: bool
    proactive_assistance: bool

    # Temporal/pacing
    response_pacing: str
    animation_speed: str
    ui_density: str

    # Emotional support
    emotional_support_level: float = Field(ge=0.0, le=1.0)
    recovery_support: bool

    # Explainability
    reasoning: list[str] = []
    contributing_factors: dict = {}
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    # Metadata
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    session_id: str = ""
    prior_mode: str | None = None

    # Runtime lineage — minted at ingestion, forwarded unchanged
    lineage_id: str | None = None
    created_monotonic: float | None = None
    event_timestamp: datetime | None = None

    model_config = ConfigDict(extra="allow")


class OrchestrationContext(BaseModel):
    """Input to the orchestrator. Wraps RichHumanState + session context."""

    session_id: str
    human_state: dict
    prior_strategy: UXStrategy | None = None
    session_message_count: int = 0
    session_duration_seconds: float = 0.0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
