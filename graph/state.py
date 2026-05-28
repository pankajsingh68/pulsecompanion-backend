"""Graph state definition for the PulseCompanion orchestration pipeline."""

from typing import TypedDict


class GraphState(TypedDict):
    """State schema passed through the LangGraph orchestration nodes."""

    user_message: str
    session_id: str
    biometric_hint: dict | None
    human_state: dict
    ux_mode: str
    transformed_prompt: str
    retrieved_memories: list[str]
    llm_response: str
    final_response: dict
