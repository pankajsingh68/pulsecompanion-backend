"""Lineage tracking — runtime-owned lineage that flows through the pipeline.

Lineage is generated ONCE at the sensor ingestion boundary and flows
forward unchanged through every downstream stage.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4


@dataclass
class LineageContext:
    """Lineage context that accompanies data through the pipeline.

    Generated once at sensor ingestion. Never reassigned.
    Every stage reads this context and includes it in emitted events.
    """
    lineage_id: UUID = field(default_factory=uuid4)
    created_monotonic: float = field(default_factory=time.monotonic)
    event_timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    session_id: str = ""
    source: str = "unknown"

    def elapsed_ms(self) -> float:
        """Milliseconds since lineage was created."""
        return (time.monotonic() - self.created_monotonic) * 1000


def mint_lineage(session_id: str, source: str = "sensor") -> LineageContext:
    """Mint a new lineage context at the sensor ingestion boundary.

    This is the ONLY place lineage is created. All downstream stages
    receive and forward this context unchanged.

    Args:
        session_id: The session this lineage belongs to.
        source: Origin of the event (sensor, manual, simulated).

    Returns:
        Fresh LineageContext with unique ID and monotonic timestamp.
    """
    return LineageContext(
        session_id=session_id,
        source=source,
    )
