"""Semantic self-model — learns user preferences over time."""

from __future__ import annotations

from datetime import datetime, timezone

from utils.logger import get_logger

logger = get_logger(__name__)


class SemanticSelfModel:
    """Learns user preferences over time via engagement signals."""

    COLLECTION_NAME = "pulse_self_model"

    def __init__(self, chroma_client, embedding_function) -> None:
        self._collection = chroma_client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            embedding_function=embedding_function,
        )
        self._preference_buffer: dict[str, list] = {
            "tone_preferences": [],
            "verbosity_preferences": [],
        }

    def record_preference_signal(
        self, ux_strategy: dict, engagement: float
    ) -> None:
        """Record a preference signal. High engagement = strategy worked."""
        if engagement > 0.6:
            tone = ux_strategy.get("response_tone")
            verbosity = ux_strategy.get("verbosity_level")
            if tone:
                self._preference_buffer["tone_preferences"].append(tone)
            if verbosity:
                self._preference_buffer["verbosity_preferences"].append(verbosity)

    def get_preference_summary(self) -> dict:
        """Return current learned preferences from buffer."""
        tones = self._preference_buffer["tone_preferences"]
        verbosities = self._preference_buffer["verbosity_preferences"]
        return {
            "preferred_tone": (
                max(set(tones), key=tones.count) if tones else "neutral"
            ),
            "preferred_verbosity": (
                max(set(verbosities), key=verbosities.count)
                if verbosities else "normal"
            ),
            "sample_count": len(tones),
            "is_reliable": len(tones) >= 5,
        }

    def store_learned_model(
        self, session_id: str, preference_summary: dict
    ) -> None:
        """Persist learned preferences to ChromaDB."""
        record_id = f"selfmodel_{session_id}"
        content = (
            f"User preference model: "
            f"tone={preference_summary.get('preferred_tone')}, "
            f"verbosity={preference_summary.get('preferred_verbosity')}, "
            f"samples={preference_summary.get('sample_count')}"
        )
        try:
            self._collection.upsert(
                ids=[record_id],
                documents=[content],
                metadatas=[{
                    "session_id": session_id,
                    "preferred_tone": preference_summary.get("preferred_tone"),
                    "preferred_verbosity": preference_summary.get("preferred_verbosity"),
                    "sample_count": preference_summary.get("sample_count", 0),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }],
            )
        except Exception as e:
            logger.warning("self_model_store_failed", error=str(e))

    def retrieve_preferences(self, session_id: str) -> dict:
        """Load previously learned preferences."""
        try:
            result = self._collection.get(ids=[f"selfmodel_{session_id}"])
            if result and result.get("metadatas"):
                return result["metadatas"][0]
            return {}
        except Exception as e:
            logger.warning("self_model_retrieval_failed", error=str(e))
            return {}
