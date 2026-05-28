"""Confidence data models."""

from pydantic import BaseModel, Field


class ModalityConfidence(BaseModel):
    """Per-signal confidence scores."""

    hr_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    hrv_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    behavioral_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    text_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    overall: float = Field(default=1.0, ge=0.0, le=1.0)


class OrchestrationConfidence(BaseModel):
    """Composite orchestration confidence."""

    modality: ModalityConfidence = ModalityConfidence()
    policy_agreement: float = Field(default=1.0, ge=0.0, le=1.0)
    state_stability: float = Field(default=1.0, ge=0.0, le=1.0)
    composite: float = Field(default=0.5, ge=0.0, le=1.0)
    is_high_confidence: bool = True
    reasoning: list[str] = []
