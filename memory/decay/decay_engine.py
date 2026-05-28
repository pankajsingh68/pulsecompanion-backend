"""Memory decay engine — time-based importance decay and reinforcement."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from utils.helpers import clamp

if TYPE_CHECKING:
    from memory.schemas import MemoryRecord


class MemoryDecayEngine:
    """Applies time-based decay to memory importance scores.

    Memories not retrieved fade. Retrieved memories get reinforced.
    High-stress memories decay slower (emotional persistence).
    """

    TIME_DECAY_HALF_LIFE_HOURS = 24

    def compute_effective_importance(
        self, record: "MemoryRecord", now: datetime | None = None
    ) -> float:
        """Compute effective importance after decay + reinforcement."""
        now = now or datetime.now(timezone.utc)

        # Time decay
        age_hours = (now - record.created_at).total_seconds() / 3600
        time_factor = self._time_decay(age_hours)

        # Recency boost
        recency_hours = (now - record.last_accessed).total_seconds() / 3600
        recency_factor = self._time_decay(recency_hours * 0.5)

        # Reinforcement
        reinforcement = min(1.0 + record.reinforcement_count * 0.15, 2.0)

        # Emotional persistence
        emotional_persistence = 1.0 + record.stress_at_creation * 0.3

        effective = (
            record.importance_score
            * time_factor
            * recency_factor
            * reinforcement
            * emotional_persistence
            * record.decay_factor
        )
        return clamp(effective)

    def _time_decay(self, age_hours: float) -> float:
        """Exponential decay with configurable half-life."""
        lambda_val = math.log(2) / self.TIME_DECAY_HALF_LIFE_HOURS
        return math.exp(-lambda_val * age_hours)

    def should_prune(
        self, record: "MemoryRecord", threshold: float = 0.05
    ) -> bool:
        """Returns True if memory has decayed below pruning threshold."""
        return self.compute_effective_importance(record) < threshold
