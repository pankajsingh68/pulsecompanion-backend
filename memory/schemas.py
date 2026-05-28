"""Schema definitions for ChromaDB memory documents."""

from typing import TypedDict


class MemoryDocument(TypedDict):
    """Schema for documents stored in ChromaDB.

    Attributes:
        content: Combined message + response text
        session_id: The session identifier
        ux_mode: The UX mode active during the interaction
        stress: The stress level at time of interaction (0.0-1.0)
        timestamp: ISO format UTC timestamp
    """

    content: str
    session_id: str
    ux_mode: str
    stress: float
    timestamp: str


# ---------------------------------------------------------------------------
# Phase 5: Cognitive Memory schemas
# ---------------------------------------------------------------------------

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class MemoryTier(str, Enum):
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    TEMPORAL = "temporal"


class MemoryImportance(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EpisodeType(str, Enum):
    BURNOUT_SIGNAL = "burnout_signal"
    RECOVERY_EVENT = "recovery_event"
    OVERLOAD_EVENT = "overload_event"
    FLOW_STATE = "flow_state"
    EMOTIONAL_SHIFT = "emotional_shift"
    STRESS_SPIKE = "stress_spike"
    FATIGUE_ACCUMULATION = "fatigue_accumulation"
    POSITIVE_ENGAGEMENT = "positive_engagement"


class MemoryRecord(BaseModel):
    """Universal memory record across all tiers."""

    record_id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: str
    tier: MemoryTier
    content: str
    importance_score: float = Field(ge=0.0, le=1.0)
    importance_label: MemoryImportance
    emotional_valence: float = Field(default=0.0, ge=-1.0, le=1.0)
    stress_at_creation: float = 0.0
    fatigue_at_creation: float = 0.0
    ux_mode_at_creation: str = "normal"
    episode_type: EpisodeType | None = None
    decay_factor: float = 1.0
    reinforcement_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_accessed: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict = {}

    model_config = ConfigDict(extra="allow")


class ImportanceScore(BaseModel):
    """Output of MemoryImportanceScorer."""

    score: float = Field(ge=0.0, le=1.0)
    label: MemoryImportance
    contributing_factors: dict = {}
    should_store: bool = True
    recommended_tier: MemoryTier = MemoryTier.WORKING
    episode_type: EpisodeType | None = None


class RetrievalResult(BaseModel):
    """Output of MemoryRetrievalRouter."""

    working_context: list[str] = []
    episodic_context: list[str] = []
    semantic_context: list[str] = []
    temporal_context: dict = {}
    combined_context: list[str] = []
    retrieval_latency_ms: float = 0.0
    tiers_consulted: list[MemoryTier] = []
    total_memories_scanned: int = 0
