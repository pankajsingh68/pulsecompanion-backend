"""Sensor data models for PulseCompanion."""

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class SensorType(str, Enum):
    HEART_RATE = "heart_rate"
    HRV = "hrv"
    GSR = "gsr"
    ACCELEROMETER = "accelerometer"
    SKIN_TEMP = "skin_temp"
    BLOOD_OXYGEN = "blood_oxygen"
    ACTIVITY = "activity"


class SensorSource(str, Enum):
    SAMSUNG_WATCH = "samsung_watch"
    APPLE_WATCH = "apple_watch"
    FITBIT = "fitbit"
    MANUAL = "manual"
    MOCK = "mock"


class SensorEvent(BaseModel):
    """Normalized sensor event. All sensor data becomes this model."""

    sensor_type: SensorType
    value: float
    unit: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source_device: SensorSource = SensorSource.MANUAL
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    sampling_rate_hz: float | None = None
    session_id: str = ""
    metadata: dict = {}

    model_config = ConfigDict(extra="allow")


class BiometricSnapshot(BaseModel):
    """Aggregated sensor readings at a point in time."""

    session_id: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    hr: float | None = None
    hrv: float | None = None
    gsr: float | None = None
    skin_temp: float | None = None
    blood_oxygen: float | None = None
    source: SensorSource = SensorSource.MANUAL
    overall_confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    # Runtime lineage — minted at ingestion boundary, forwarded unchanged
    lineage_id: str | None = None
    created_monotonic: float | None = None
    event_timestamp: datetime | None = None
