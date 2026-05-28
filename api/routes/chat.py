"""Chat endpoint for PulseCompanion backend."""

from fastapi import APIRouter, Request

from models.request import ChatRequest
from models.response import AdaptiveResponse
from graph.builder import build_graph
from websocket.events import state_update_event, response_event
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()

# Build graph once at module level
_graph = build_graph()


@router.post("/api/chat", response_model=AdaptiveResponse)
async def chat(request_body: ChatRequest, request: Request):
    """Process a chat message through the PulseCompanion orchestration graph.

    Accepts a ChatRequest, runs the LangGraph pipeline (state estimation,
    prompt transformation, LLM call, response adaptation), stores the
    interaction in memory, sends WebSocket events, and returns an
    AdaptiveResponse.

    Args:
        request_body: The incoming chat request with message, session_id, and optional biometric_hint.
        request: FastAPI Request object for accessing shared app state.

    Returns:
        AdaptiveResponse with reply, human_state, ux_mode, memory_anchors, and metadata.
    """
    # Prepare initial graph state
    initial_state = {
        "user_message": request_body.message,
        "session_id": request_body.session_id,
        "biometric_hint": request_body.biometric_hint,
        "human_state": {},
        "ux_mode": "",
        "transformed_prompt": "",
        "retrieved_memories": [],
        "llm_response": "",
        "final_response": {},
    }

    # Execute the orchestration graph
    result = await _graph.ainvoke(initial_state)

    final_response = result["final_response"]

    # Store interaction in memory (best effort)
    try:
        memory_mgr = request.app.state.memory_manager
        memory_mgr.store_interaction(
            session_id=request_body.session_id,
            message=request_body.message,
            response=final_response["reply"],
            human_state=final_response["human_state"],
        )
    except Exception as e:
        logger.warning("memory_store_skipped", error=str(e))

    # Send WebSocket events (best effort)
    try:
        ws_manager = request.app.state.ws_manager
        human_state_dict = final_response["human_state"]
        if isinstance(human_state_dict, dict):
            hs_dict = human_state_dict
        else:
            hs_dict = human_state_dict.model_dump() if hasattr(human_state_dict, "model_dump") else dict(human_state_dict)

        # Send STATE_UPDATE event
        await ws_manager.send_event(
            request_body.session_id,
            state_update_event(hs_dict, final_response["ux_mode"]),
        )
        # Send RESPONSE event
        await ws_manager.send_event(
            request_body.session_id,
            response_event(
                reply=final_response["reply"],
                human_state=hs_dict,
                ux_mode=final_response["ux_mode"],
                memory_anchors=final_response.get("memory_anchors", []),
                metadata=final_response.get("response_metadata", {}),
            ),
        )
    except Exception as e:
        logger.warning("ws_event_skipped", error=str(e))

    # Update session state store for the /api/state/current endpoint
    try:
        from api.routes.state import _session_states

        _session_states[request_body.session_id] = final_response["human_state"]
    except Exception:
        pass

    return AdaptiveResponse(**final_response)
