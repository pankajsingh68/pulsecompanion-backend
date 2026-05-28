"""State endpoint for PulseCompanion backend."""

from datetime import datetime, timezone

from fastapi import APIRouter, Query

from models.human_state import HumanState

router = APIRouter()

# In-memory store for last known session states (populated by chat endpoint)
_session_states: dict[str, dict] = {}


@router.get("/api/state/current")
async def get_current_state(session_id: str = Query(..., min_length=1)):
    """Return the last known HumanState for a given session.

    If no state exists for the session, returns a default neutral state.

    Args:
        session_id: The session identifier to look up.

    Returns:
        HumanState dict with stress, focus, fatigue, confidence, ux_mode, and timestamp.
    """
    state = _session_states.get(session_id)
    if state:
        return state

    # Return default state if no session data exists
    return HumanState(
        stress=0.0,
        focus=0.5,
        fatigue=0.2,
        confidence=0.84,
        ux_mode="normal",
        timestamp=datetime.now(timezone.utc),
    )
