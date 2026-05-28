from pydantic import BaseModel, Field
from datetime import datetime
from typing import Literal


class HumanState(BaseModel):
    stress: float = Field(ge=0.0, le=1.0)
    focus: float = Field(ge=0.0, le=1.0)
    fatigue: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    ux_mode: Literal["normal", "calm_minimal", "focus_mode", "overload_protection"]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
