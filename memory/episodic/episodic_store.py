"""Episodic store — ChromaDB collection for emotional episodes."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from memory.schemas import EpisodeType
from utils.logger import get_logger

logger = get_logger(__name__)


class EpisodicStore:
    """Stores emotionally significant events in a separate ChromaDB collection."""

    COLLECTION_NAME = "pulse_episodic_memory"

    def __init__(self, chroma_client, embedding_function) -> None:
        self._collection = chroma_client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            embedding_function=embedding_function,
            metadata={"description": "Emotional episode memory"},
        )

    async def store_episode(
        self, session_id: str, episode_type: EpisodeType,
        human_state: dict, message_context: str,
    ) -> str:
        """Store one episodic memory. Returns record_id."""
        record_id = str(uuid4())
        stress = human_state.get("stress", 0)
        fatigue = human_state.get("fatigue", 0)
        focus = human_state.get("focus", 0)
        ux_mode = human_state.get("ux_mode", "normal")

        content = self._build_narrative(
            episode_type, stress, fatigue, focus, ux_mode, message_context
        )

        try:
            self._collection.add(
                ids=[record_id],
                documents=[content],
                metadatas=[{
                    "session_id": session_id,
                    "episode_type": episode_type.value,
                    "stress": stress,
                    "fatigue": fatigue,
                    "focus": focus,
                    "ux_mode": ux_mode,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }],
            )
            logger.info("episode_stored", session_id=session_id,
                       episode_type=episode_type.value, record_id=record_id)
        except Exception as e:
            logger.error("episode_store_failed", error=str(e))

        return record_id

    def retrieve_relevant_episodes(
        self, session_id: str, query: str, n: int = 3
    ) -> list[str]:
        """Retrieve episodes relevant to current context."""
        try:
            results = self._collection.query(
                query_texts=[query], n_results=n,
                where={"session_id": session_id},
            )
            docs = results.get("documents", [[]])[0]
            return docs if docs else []
        except Exception as e:
            logger.warning("episodic_retrieval_failed", error=str(e))
            return []

    def _build_narrative(
        self, episode_type: EpisodeType, stress: float, fatigue: float,
        focus: float, ux_mode: str, context: str,
    ) -> str:
        """Build human-readable episode description for embedding."""
        templates = {
            EpisodeType.BURNOUT_SIGNAL: f"Burnout signals: stress={stress:.2f}, fatigue={fatigue:.2f}. {context[:100]}",
            EpisodeType.FLOW_STATE: f"Deep focus flow: focus={focus:.2f}, stress={stress:.2f}. {context[:100]}",
            EpisodeType.OVERLOAD_EVENT: f"Cognitive overload: mode={ux_mode}, stress={stress:.2f}. {context[:100]}",
            EpisodeType.RECOVERY_EVENT: f"Recovery from stress: stress={stress:.2f}. {context[:100]}",
            EpisodeType.STRESS_SPIKE: f"Acute stress spike: stress={stress:.2f}. {context[:100]}",
            EpisodeType.FATIGUE_ACCUMULATION: f"Sustained fatigue: fatigue={fatigue:.2f}. {context[:100]}",
            EpisodeType.EMOTIONAL_SHIFT: f"Emotional shift: stress={stress:.2f}, mode={ux_mode}. {context[:100]}",
            EpisodeType.POSITIVE_ENGAGEMENT: f"Positive engagement: focus={focus:.2f}. {context[:100]}",
        }
        return templates.get(episode_type, f"Event: {episode_type.value}. stress={stress:.2f}")
