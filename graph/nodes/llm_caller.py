"""LLM caller node for the orchestration graph."""

import httpx

from graph.state import GraphState
from orchestration.modes import NUM_PREDICT_MAP
from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)


async def call_llm_node(state: GraphState) -> dict:
    """Send the transformed prompt to Ollama and return the LLM response.

    Uses the phi3:mini model with mode-based num_predict limits.
    Handles timeout (30s), connection errors, and empty responses gracefully.
    """
    ux_mode = state["ux_mode"]
    num_predict = NUM_PREDICT_MAP.get(ux_mode, 512)

    payload = {
        "model": settings.OLLAMA_MODEL,
        "prompt": state["transformed_prompt"],
        "stream": False,
        "options": {
            "temperature": 0.7,
            "num_predict": num_predict,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.OLLAMA_BASE_URL}/api/generate",
                json=payload,
            )
            response.raise_for_status()
            result = response.json()
            llm_response = result.get("response", "")
            if not llm_response:
                llm_response = "I'm here to help. Could you tell me more?"
            return {"llm_response": llm_response}
    except httpx.TimeoutException:
        logger.error("llm_timeout", ux_mode=ux_mode)
        return {
            "llm_response": "I'm having trouble connecting right now. Please try again in a moment."
        }
    except httpx.ConnectError:
        logger.error("llm_connection_error", ux_mode=ux_mode)
        return {
            "llm_response": "I'm having trouble connecting right now. Please try again in a moment."
        }
    except Exception as e:
        logger.error("llm_call_failed", error=str(e), ux_mode=ux_mode)
        return {"llm_response": "Something went wrong. Let me try again."}
