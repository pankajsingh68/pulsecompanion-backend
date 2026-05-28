"""State estimator node for the orchestration graph."""

from graph.state import GraphState
from emotion.estimator import HeuristicStateEstimator

estimator = HeuristicStateEstimator()


def estimate_state_node(state: GraphState) -> dict:
    """Estimate the user's cognitive/emotional state from message and biometrics.

    Calls the HeuristicStateEstimator and writes human_state and ux_mode
    to the graph state.
    """
    human_state = estimator.estimate_state(
        message=state["user_message"],
        biometric_hint=state.get("biometric_hint"),
    )
    return {
        "human_state": human_state.model_dump(mode="json"),
        "ux_mode": human_state.ux_mode,
    }
