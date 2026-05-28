"""Safety data models for bounded adaptation."""

from pydantic import BaseModel


class AdaptationBounds(BaseModel):
    """Hard limits on per-turn adaptation changes."""

    max_tone_shift_per_turn: int = 1
    max_verbosity_shift_per_turn: int = 1
    max_emotional_support_delta: float = 0.3
    max_notification_delay_jump: int = 60
    min_mode_hold_seconds: float = 15.0
    max_consecutive_break_suggestions: int = 2


class SafetyGuardResult(BaseModel):
    """Result of safety guard enforcement."""

    was_limited: bool = False
    original_strategy: dict = {}
    limited_fields: list[str] = []
    reasoning: str = ""

    # Runtime lineage — forwarded from the orchestration decision it corrected
    lineage_id: str | None = None
