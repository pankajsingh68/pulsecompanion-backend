"""Memory consolidator — background compression and self-model flushing."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from utils.logger import get_logger

if TYPE_CHECKING:
    from memory.decay.decay_engine import MemoryDecayEngine
    from memory.semantic.self_model import SemanticSelfModel

logger = get_logger(__name__)


class MemoryConsolidator:
    """Background consolidation: flushes self-model, prunes decayed memories."""

    CONSOLIDATION_EVERY_N = 10

    def __init__(
        self,
        self_model: "SemanticSelfModel",
        decay_engine: "MemoryDecayEngine",
    ) -> None:
        self.self_model = self_model
        self.decay = decay_engine
        self._message_counter: dict[str, int] = {}

    def should_consolidate(self, session_id: str) -> bool:
        count = self._message_counter.get(session_id, 0)
        return count > 0 and count % self.CONSOLIDATION_EVERY_N == 0

    def increment(self, session_id: str) -> None:
        self._message_counter[session_id] = (
            self._message_counter.get(session_id, 0) + 1
        )

    async def consolidate(self, session_id: str) -> dict:
        """Run consolidation for a session."""
        start = datetime.now(timezone.utc)
        actions_taken: list[str] = []

        # Flush self-model preferences to ChromaDB
        prefs = self.self_model.get_preference_summary()
        if prefs.get("sample_count", 0) >= 3:
            self.self_model.store_learned_model(session_id, prefs)
            actions_taken.append("self_model_flushed")

        elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000

        logger.info(
            "consolidation_complete",
            session_id=session_id,
            actions=actions_taken,
            latency_ms=round(elapsed, 2),
        )

        return {
            "session_id": session_id,
            "actions_taken": actions_taken,
            "latency_ms": round(elapsed, 2),
        }
