"""Simulation data models — Pydantic v2 only, no logic."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SensorSnapshot(BaseModel):
    """A single point-in-time sensor reading from simulation."""

    session_id: str
    timestamp: float
    hr: float | None = None
    hrv: float | None = None
    gsr: float | None = None
    spo2: float | None = None
    fatigue_index: float | None = None
    source: Literal["simulated", "real", "injected"] = "simulated"
    quality: float = Field(default=1.0, ge=0.0, le=1.0)


class EmotionalTrajectory(BaseModel):
    """Defines an emotional pattern to simulate."""

    pattern: Literal["burnout", "recovery", "focus", "anxiety_spike", "calm"]
    duration_seconds: float = 60.0
    intensity: float = Field(default=0.7, ge=0.0, le=1.0)
    seed: int | None = None


class RuntimeScenario(BaseModel):
    """A chaos/stress test scenario definition."""

    name: str
    description: str = ""
    duration_seconds: float = 60.0
    components: list[Literal[
        "sensor_dropout", "websocket_flood", "recompute_storm",
        "recovery_sequence", "fatigue_accumulation", "oscillating_states",
        "high_stress_overload", "timestamp_drift",
    ]] = []
    seed: int | None = None


class SimulatedSession(BaseModel):
    """Configuration for a full simulated session."""

    session_id: str
    user_profile: dict = {}
    trajectory: EmotionalTrajectory
    scenario: RuntimeScenario | None = None
    sampling_interval_ms: int = 100


class ChaosEvent(BaseModel):
    """A single chaos event that was triggered during testing."""

    event_type: str
    triggered_at: float
    payload: dict = {}
    expected_recovery_within_seconds: float = 10.0


class ScenarioResult(BaseModel):
    """Result of running a complete scenario."""

    passed: bool
    duration_seconds: float
    events_triggered: int
    metrics_snapshot: dict = {}
    errors: list[str] = []


class ChaosReport(BaseModel):
    """Full report from a chaos run."""

    scenario_name: str
    started_at: float
    duration_seconds: float
    events: list[ChaosEvent] = []
    recovery_validated: bool = False
    resilience_score: float = 0.0


class RecoveryResult(BaseModel):
    """Result of recovery validation."""

    recovered: bool
    time_to_recovery_seconds: float = 0.0
    oscillations_detected: int = 0
    final_state: str = "unknown"
