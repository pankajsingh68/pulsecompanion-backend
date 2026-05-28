"""Health check endpoint for PulseCompanion backend."""

from fastapi import APIRouter
import httpx
import chromadb

from config import settings

router = APIRouter()


@router.get("/api/health")
async def health_check():
    """Check connectivity to Ollama and ChromaDB.

    Returns:
        Dict with overall status and individual service health booleans.
    """
    ollama_ok = False
    chromadb_ok = False

    # Check Ollama connectivity
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            ollama_ok = resp.status_code == 200
    except Exception:
        pass

    # Check ChromaDB collection access
    try:
        client = chromadb.PersistentClient(path=settings.CHROMADB_PATH)
        client.get_or_create_collection(name=settings.CHROMADB_COLLECTION)
        chromadb_ok = True
    except Exception:
        pass

    return {"status": "ok", "ollama": ollama_ok, "chromadb": chromadb_ok}
