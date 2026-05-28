"""Cognitive Memory System — single public entry point for Phase 5.

Wraps all memory tiers: working, episodic, semantic, temporal.
Provides store(), retrieve(), observe_strategy() methods.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from memory.consolidation.consolidator import MemoryConsolidator
from memory.decay.decay_engine import MemoryDecayEngine
from memory.episodic.episode_detector import EpisodeDetector
from memory.episodic.episodic_store import EpisodicStore
from memory.retrieval.retrieval_router import MemoryRetrievalRouter
from memory.schemas import MemoryTier, RetrievalResult
from memory.scoring.importance_scorer import MemoryImportanceScorer
from memory.semantic.self_model import SemanticSelfModel
from memory.temporal.baseline_memory import TemporalBaselineMemory
from memory.working.working_memory import WorkingMemory
from utils.logger import get_logger

if TYPE_CHECKING:
    from memory.manager import MemoryManager

logger = get_logger(__name__)


class CognitiveMemorySystem:
    """Single entry point for all Phase 5 memory operations.

    Wraps all tiers. Provides three public async methods:
    - store()    → rich memory storage with importance scoring
    - retrieve() → multi-tier retrieval with merging
    - observe_strategy() → records preference signals
    """

    def __init__(
        self,
        session_id: str,
        existing_manager: "MemoryManager",
        chroma_client,
        embedding_function,
    ) -> None:
        self.session_id = session_id
        self.legacy = existing_manager

        # Initialize all tiers
        self.working = WorkingMemory(session_id)
        self.episodic_store = EpisodicStore(chroma_client, embedding_function)
        self.self_model = SemanticSelfModel(chroma_client, embedding_function)
        self.temporal = TemporalBaselineMemory(session_id)
        self.decay_engine = MemoryDecayEngine()
        self.scorer = MemoryImportanceScorer()
        self.episode_detector = EpisodeDetector()
        self.consolidator = MemoryConsolidator(self.self_model, self.decay_engine)

        self.retrieval_router = MemoryRetrievalRouter(
            working_memory=self.working,
            episodic_store=self.episodic_store,
            self_model=self.self_model,
            temporal_baseline=self.temporal,
            existing_manager=existing_manager,
            decay_engine=self.decay_engine,
        )

        self._message_count = 0

    async def store(
        self,
        message: str,
        response: str,
        human_state: dict,
        biometric_hint: dict | None = None,
        ux_strategy: dict | None = None,
        prior_state: dict | None = None,
    ) -> dict:
        """Full cognitive store pipeline. Returns observability dict."""
        self._message_count += 1
        self.consolidator.increment(self.session_id)

        # Always store to existing ChromaDB (backward compat)
        try:
            self.legacy.store_interaction(
                self.session_id, message, response, human_state
            )
        except Exception as e:
            logger.warning("legacy_store_failed", error=str(e))

        # Score importance
        state_history = self.working.get_state_history()
        scored = self.scorer.score(message, human_state, prior_state, state_history)

        # Update working memory
        self.working.add(message, response, human_state, scored.score)

        # Update temporal baseline
        self.temporal.update(human_state, biometric_hint)

        # Detect episodes
        confirmed_episode = self.episode_detector.update(human_state, scored)

        # Store episodic if significant
        if (scored.recommended_tier == MemoryTier.EPISODIC
                or confirmed_episode is not None):
            episode_type = confirmed_episode or scored.episode_type
            if episode_type:
                await self.episodic_store.store_episode(
                    self.session_id, episode_type, human_state, message[:200]
                )

        # Record preference signal from UX strategy
        if ux_strategy:
            engagement = human_state.get("engagement", 0.5)
            self.self_model.record_preference_signal(ux_strategy, engagement)

        # Background consolidation if due
        if self.consolidator.should_consolidate(self.session_id):
            # Store task reference (not fire-and-forget in production,
            # but consolidation is non-critical background work)
            asyncio.ensure_future(
                self.consolidator.consolidate(self.session_id)
            )

        return {
            "importance_score": scored.score,
            "importance_label": scored.label.value,
            "tier_stored": scored.recommended_tier.value,
            "episode_detected": (
                confirmed_episode.value if confirmed_episode else None
            ),
            "working_memory_size": len(self.working),
        }

    async def retrieve(self, query: str, human_state: dict) -> RetrievalResult:
        """Full cognitive retrieval across all tiers."""
        return await self.retrieval_router.retrieve(
            session_id=self.session_id,
            query=query,
            human_state=human_state,
            session_message_count=self._message_count,
        )

    async def observe_strategy(
        self, ux_strategy: dict, engagement: float
    ) -> None:
        """Record which UX strategies correlate with engagement."""
        self.self_model.record_preference_signal(ux_strategy, engagement)
