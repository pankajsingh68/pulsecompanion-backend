"""ChromaDB memory manager for storing and retrieving interactions."""

import uuid
from datetime import datetime, timezone

import chromadb
from chromadb.utils.embedding_functions import OllamaEmbeddingFunction

from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)


class MemoryManager:
    """Manages interaction storage and retrieval using ChromaDB.

    Uses Ollama's nomic-embed-text model for semantic embeddings
    and provides session-scoped memory operations.
    """

    # Phase 5: Set False to revert to Phase 1 behavior entirely
    USE_COGNITIVE_MEMORY = True

    def __init__(self) -> None:
        """Initialize ChromaDB client, embedding function, and collection."""
        try:
            self.client = chromadb.PersistentClient(path=settings.CHROMADB_PATH)
            self.embedding_fn = OllamaEmbeddingFunction(
                url=f"{settings.OLLAMA_BASE_URL}/api/embeddings",
                model_name=settings.OLLAMA_EMBED_MODEL,
            )
            self.collection = self.client.get_or_create_collection(
                name=settings.CHROMADB_COLLECTION,
                embedding_function=self.embedding_fn,
            )
            logger.info("memory_manager_initialized", collection=settings.CHROMADB_COLLECTION)
        except Exception as e:
            logger.error("memory_manager_init_failed", error=str(e))
            raise

    def store_interaction(
        self, session_id: str, message: str, response: str, human_state: dict
    ) -> None:
        """Store a chat interaction in ChromaDB.

        Args:
            session_id: The session identifier.
            message: User's message text.
            response: AI assistant's response text.
            human_state: Dict with stress, ux_mode, etc.
        """
        doc_id = str(uuid.uuid4())
        content = f"User: {message}\nAssistant: {response}"
        metadata = {
            "session_id": session_id,
            "ux_mode": human_state.get("ux_mode", "normal"),
            "stress": human_state.get("stress", 0.0),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        try:
            self.collection.add(
                ids=[doc_id],
                documents=[content],
                metadatas=[metadata],
            )
            logger.info("memory_stored", session_id=session_id, doc_id=doc_id)
        except Exception as e:
            logger.error("memory_store_failed", error=str(e), session_id=session_id)

    def retrieve_context(
        self, session_id: str, query: str, n_results: int = 3
    ) -> list[str]:
        """Retrieve the top N most relevant memories for a session.

        Uses semantic search via the Ollama embedding function to find
        the most contextually relevant past interactions.

        Args:
            session_id: Filter results to this session.
            query: The query text for semantic search.
            n_results: Number of results to return (default 3).

        Returns:
            List of relevant memory document strings.
        """
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                where={"session_id": session_id},
            )
            documents = results.get("documents", [[]])[0]
            return documents if documents else []
        except Exception as e:
            logger.error("memory_retrieve_failed", error=str(e), session_id=session_id)
            return []

    def get_session_trend(self, session_id: str) -> dict:
        """Get average stress and interaction count trends for a session.

        Args:
            session_id: The session to analyze.

        Returns:
            Dict with avg_stress (float) and interaction_count (int).
        """
        try:
            results = self.collection.get(
                where={"session_id": session_id},
            )
            metadatas = results.get("metadatas", [])
            if not metadatas:
                return {"avg_stress": 0.0, "interaction_count": 0}

            stresses = [m.get("stress", 0.0) for m in metadatas]
            return {
                "avg_stress": sum(stresses) / len(stresses),
                "interaction_count": len(metadatas),
            }
        except Exception as e:
            logger.error("session_trend_failed", error=str(e), session_id=session_id)
            return {"avg_stress": 0.0, "interaction_count": 0}

    def get_cognitive_system(
        self,
        session_id: str,
        chroma_client=None,
        embedding_function=None,
    ):
        """Returns CognitiveMemorySystem for session if enabled.

        Returns None if USE_COGNITIVE_MEMORY = False.
        Caller falls back to direct store_interaction/retrieve_context.
        """
        if not self.USE_COGNITIVE_MEMORY:
            return None

        try:
            from memory.cognitive_memory import CognitiveMemorySystem

            client = chroma_client or self.client
            embed_fn = embedding_function or self.embedding_fn

            return CognitiveMemorySystem(
                session_id=session_id,
                existing_manager=self,
                chroma_client=client,
                embedding_function=embed_fn,
            )
        except Exception as e:
            logger.warning("cognitive_memory_init_failed", error=str(e))
            return None
