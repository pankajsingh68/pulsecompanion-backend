"""Response adapter node for the orchestration graph."""

from graph.state import GraphState


def adapt_response_node(state: GraphState) -> dict:
    """Format the final AdaptiveResponse dict from graph state.

    Assembles reply, human_state, ux_mode, memory_anchors (top 3),
    and response metadata into the final_response field.
    """
    final_response = {
        "reply": state["llm_response"],
        "human_state": state["human_state"],
        "ux_mode": state["ux_mode"],
        "memory_anchors": state["retrieved_memories"][:3],
        "response_metadata": {
            "adapted_for": state["ux_mode"],
            "prompt_version": f"{state['ux_mode']}_v1",
        },
    }
    return {"final_response": final_response}
