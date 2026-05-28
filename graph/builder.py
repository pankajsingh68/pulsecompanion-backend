"""LangGraph orchestration graph builder for PulseCompanion."""

from langgraph.graph import StateGraph, START, END

from graph.state import GraphState
from graph.nodes.state_estimator import estimate_state_node
from graph.nodes.prompt_transformer import transform_prompt_node
from graph.nodes.llm_caller import call_llm_node
from graph.nodes.response_adapter import adapt_response_node


def build_graph():
    """Build and compile the PulseCompanion orchestration graph.

    Pipeline: START → estimate_state → transform_prompt → call_llm → adapt_response → END

    Returns:
        A compiled LangGraph StateGraph ready for invocation.
    """
    graph = StateGraph(GraphState)

    graph.add_node("estimate_state", estimate_state_node)
    graph.add_node("transform_prompt", transform_prompt_node)
    graph.add_node("call_llm", call_llm_node)
    graph.add_node("adapt_response", adapt_response_node)

    graph.add_edge(START, "estimate_state")
    graph.add_edge("estimate_state", "transform_prompt")
    graph.add_edge("transform_prompt", "call_llm")
    graph.add_edge("call_llm", "adapt_response")
    graph.add_edge("adapt_response", END)

    return graph.compile()
