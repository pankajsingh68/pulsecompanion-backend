"""Retrieval router — multi-tier memory retrieval with merging."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from memory.schemas import MemoryTier, RetrievalResult
from utils.logger import get_logger

if TYPE_CHECKING:
    from memory.decay.decay_engine import MemoryDecayEngine
    from memory.episodic.episodic_store import EpisodicStore
    from memory.manager import MemoryManager
    from memory.semantic.self_model import SemanticSelfModel
    from memory.temporal.baseline_memory import TemporalBaselineMemory
    from memory.working.working_memory import WorkingMemory

logger = get_logger(__name__)


class MemoryRetrievalRouter:
    """Routes retrieval across all memory tiers. Returns merged context."""

    EMOTIONAL_KEYWORDS = [
        "stressed", "tired", "focused", "overwhelmed", "anxious",
        "burnout", "exhausted", "deadline", "pressure", "flow",
        "distracted", "energized", "motivated",
    ]

    def __init__(
        self,
        working_memory: "WorkingMemory",
        episodic_store: "EpisodicStore",
        self_model: "SemanticSelfModel",
        temporal_baseline: "TemporalBaselineMemory",
        existing_manager: "MemoryManager",
        decay_engine: "MemoryDecayEngine",
    ) -> None:
        self.working = working_memory
        self.episodic = episodic_store
        self.self_model = self_model
        self.temporal = temporal_baseline
        self.legacy = existing_manager
        self.decay = decay_engine

    async def retrieve(
        self,
        session_id: str,
        query: str,
        human_state: dict,
        session_message_count: int = 0,
    ) -> RetrievalResult:
        """Retrieve context from all applicable tiers."""
        start = datetime.now(timezone.utc)
        tiers_consulted: list[MemoryTier] = []
        total_scanned = 0

        # Tier 1: Working memory (always)
        working_ctx = self.working.get_context_strings(n=4)
        tiers_consulted.append(MemoryTier.WORKING)
        total_scanned += len(working_ctx)

        # Tier 2: Legacy ChromaDB
        legacy_ctx: list[str] = []
        try:
            legacy_ctx = self.legacy.retrieve_context(session_id, query, n_results=2)
            total_scanned += len(legacy_ctx)
        except Exception as e:
            logger.warning("legacy_retrieval_failed", error=str(e))

        # Tier 3: Episodic (if emotional context or high stress)
        episodic_ctx: list[str] = []
        stress = human_state.get("stress", 0)
        fatigue = human_state.get("fatigue", 0)
        is_emotional = any(kw in query.lower() for kw in self.EMOTIONAL_KEYWORDS)

        if is_emotional or stress > 0.5 or fatigue > 0.5:
            episodic_ctx = self.episodic.retrieve_relevant_episodes(
                session_id, query, n=2
            )
            tiers_consulted.append(MemoryTier.EPISODIC)
            total_scanned += len(episodic_ctx)

        # Tier 4: Semantic self-model (if enough history)
        semantic_ctx: list[str] = []
        if session_message_count >= 5:
            prefs = self.self_model.get_preference_summary()
            if prefs.get("is_reliable"):
                semantic_ctx = [
                    f"User preference: tone={prefs.get('preferred_tone')}, "
                    f"verbosity={prefs.get('preferred_verbosity')} "
                    f"(from {prefs.get('sample_count')} interactions)"
                ]
                tiers_consulted.append(MemoryTier.SEMANTIC)
                total_scanned += 1

        # Tier 5: Temporal baseline (always)
        temporal_str = self.temporal.get_context_string()
        tiers_consulted.append(MemoryTier.TEMPORAL)
        total_scanned += 1

        # Merge + deduplicate
        combined = self._merge(
            working_ctx, episodic_ctx, semantic_ctx, legacy_ctx, temporal_str
        )

        latency = (datetime.now(timezone.utc) - start).total_seconds() * 1000

        logger.debug(
            "memory_retrieved",
            session_id=session_id,
            tiers=len(tiers_consulted),
            total_ctx=len(combined),
            latency_ms=round(latency, 2),
        )

        return RetrievalResult(
            working_context=working_ctx,
            episodic_context=episodic_ctx,
            semantic_context=semantic_ctx,
            temporal_context={"baseline_summary": temporal_str},
            combined_context=combined,
            retrieval_latency_ms=round(latency, 2),
            tiers_consulted=tiers_consulted,
            total_memories_scanned=total_scanned,
        )

    def _merge(
        self, working: list, episodic: list, semantic: list,
        legacy: list, temporal_str: str,
    ) -> list[str]:
        """Priority: working > legacy > episodic > semantic > temporal."""
        merged: list[str] = []
        seen_prefixes: set[str] = set()

        all_sources = working + legacy + episodic + semantic + [temporal_str]
        for item in all_sources:
            if not item:
                continue
            prefix = item[:40]
            if prefix not in seen_prefixes:
                merged.append(item)
                seen_prefixes.add(prefix)

        return merged[:8]
