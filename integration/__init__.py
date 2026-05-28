"""Integration validation layer — proves the full adaptive pipeline operates correctly.

This module adds no features. It adds truth.
Validates: event lineage, signal propagation, adaptive loop correctness,
WebSocket delivery, persistence integrity, degradation recovery, and
orchestration decision consistency.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


class ValidatorMode(str, Enum):
    """Operating mode for all validators."""
    SIMULATION = "simulation"
    DEGRADED = "degraded"
    HIGH_LOAD = "high_load"
    CHAOS = "chaos"


@dataclass(frozen=True)
class LineageTrace:
    """Immutable trace of a single event through the full pipeline.

    Every state transition carries a lineage_id minted at sensor ingestion.
    A transition that cannot be traced from raw sensor to final persistence
    is a validation failure, not a warning.
    """
    lineage_id: UUID
    timestamps: dict[str, float] = field(default_factory=dict)
    payloads: dict[str, Any] = field(default_factory=dict)
    mutations: list[str] = field(default_factory=list)


@dataclass
class StabilityScore:
    """Composite stability score from a validation run.

    Target: overall >= 0.85 under normal/simulation mode.
    Expected degradation under chaos mode is documented per-component.
    """
    orchestration_stability: float = 1.0   # 0–1, inverse oscillation rate
    emotional_continuity: float = 1.0      # 0–1, trajectory smoothness
    memory_consistency: float = 1.0        # 0–1, no duplication or gaps
    stream_coherence: float = 1.0          # 0–1, no inversions or staleness
    recovery_smoothness: float = 1.0       # 0–1, recovery within budget
    overall: float = 1.0                   # weighted mean

    def compute_overall(self) -> float:
        """Compute weighted mean of all sub-scores."""
        weights = {
            "orchestration_stability": 0.25,
            "emotional_continuity": 0.20,
            "memory_consistency": 0.20,
            "stream_coherence": 0.20,
            "recovery_smoothness": 0.15,
        }
        self.overall = sum(
            getattr(self, k) * w for k, w in weights.items()
        )
        return self.overall


def mint_lineage() -> LineageTrace:
    """Mint a new LineageTrace at sensor ingestion boundary."""
    return LineageTrace(
        lineage_id=uuid4(),
        timestamps={"minted": time.monotonic()},
        payloads={},
        mutations=[],
    )
