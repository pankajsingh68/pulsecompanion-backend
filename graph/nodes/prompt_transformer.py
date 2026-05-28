"""Prompt transformer node for the orchestration graph."""

from graph.state import GraphState
from prompts.templates import TEMPLATES
from prompts.injector import inject_prompt
from utils.logger import get_logger

logger = get_logger(__name__)


def transform_prompt_node(state: GraphState) -> dict:
    """Retrieve memories, select template by ux_mode, and build the final prompt.

    Gracefully handles memory retrieval failures by falling back to empty memories.
    """
    ux_mode = state["ux_mode"]
    template = TEMPLATES.get(ux_mode, TEMPLATES["normal"])

    # Try to retrieve memories, gracefully handle failures
    memories: list[str] = []
    try:
        from memory.manager import MemoryManager

        memory_mgr = MemoryManager()
        memories = memory_mgr.retrieve_context(
            session_id=state["session_id"],
            query=state["user_message"],
        )
    except Exception as e:
        logger.warning("memory_retrieval_skipped", error=str(e))

    transformed_prompt = inject_prompt(template, memories, state["user_message"])

    return {
        "transformed_prompt": transformed_prompt,
        "retrieved_memories": memories,
    }
