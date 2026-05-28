"""WebSocket event factory functions for PulseCompanion."""

from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Existing events — used by api/routes/chat.py (DO NOT REMOVE)
# ---------------------------------------------------------------------------


def state_update_event(human_state: dict, ux_mode: str) -> dict:
    """Create a STATE_UPDATE event for WebSocket broadcast.

    Args:
        human_state: Current estimated human state dictionary.
        ux_mode: Current UX mode string.

    Returns:
        Event dict with type, human_state, ux_mode, and timestamp.
    """
    return {
        "type": "STATE_UPDATE",
        "human_state": human_state,
        "ux_mode": ux_mode,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def response_event(
    reply: str,
    human_state: dict,
    ux_mode: str,
    memory_anchors: list[str],
    metadata: dict,
) -> dict:
    """Create a RESPONSE event for WebSocket broadcast.

    Args:
        reply: The LLM-generated response text.
        human_state: Current estimated human state dictionary.
        ux_mode: Current UX mode string.
        memory_anchors: List of memory anchor identifiers.
        metadata: Additional response metadata.

    Returns:
        Event dict with type, reply, human_state, ux_mode, memory_anchors, and metadata.
    """
    return {
        "type": "RESPONSE",
        "reply": reply,
        "human_state": human_state,
        "ux_mode": ux_mode,
        "memory_anchors": memory_anchors,
        "metadata": metadata,
    }


def error_event(message: str, code: str) -> dict:
    """Create an ERROR event for WebSocket broadcast.

    Args:
        message: Human-readable error message.
        code: Machine-readable error code.

    Returns:
        Event dict with type, message, and code.
    """
    return {
        "type": "ERROR",
        "message": message,
        "code": code,
    }


# ---------------------------------------------------------------------------
# New events — for future streaming and UX mode transitions
# ---------------------------------------------------------------------------


def token_stream_event(session_id: str, token: str, is_final: bool = False) -> dict:
    """For future streaming LLM token delivery.

    Args:
        session_id: Target session.
        token: The token text chunk.
        is_final: Whether this is the last token in the stream.
    """
    return {
        "type": "token_stream",
        "session_id": session_id,
        "token": token,
        "is_final": is_final,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def ux_mode_change_event(
    session_id: str, old_mode: str, new_mode: str, reason: str
) -> dict:
    """Notifies frontend when UX mode changes mid-session.

    Args:
        session_id: Target session.
        old_mode: Previous UX mode.
        new_mode: New UX mode.
        reason: Human-readable reason for the change.
    """
    return {
        "type": "ux_mode_change",
        "session_id": session_id,
        "old_mode": old_mode,
        "new_mode": new_mode,
        "reason": reason,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def memory_anchor_event(session_id: str, anchors: list[str]) -> dict:
    """Pushes updated memory anchors to frontend.

    Args:
        session_id: Target session.
        anchors: List of memory anchor strings.
    """
    return {
        "type": "memory_update",
        "session_id": session_id,
        "anchors": anchors,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def system_status_event(status: str, message: str) -> dict:
    """System-level status broadcast.

    Args:
        status: Status code (e.g. "healthy", "degraded").
        message: Human-readable status message.
    """
    return {
        "type": "system_status",
        "status": status,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Phase 3 events — orchestration and sensor pipeline
# ---------------------------------------------------------------------------


def ux_strategy_event(session_id: str, strategy_dict: dict) -> dict:
    """Emit full UXStrategy to frontend."""
    return {
        "type": "ux_strategy_update",
        "session_id": session_id,
        "strategy": strategy_dict,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def cognitive_overload_event(
    session_id: str, cognitive_load: float, reasoning: list[str]
) -> dict:
    """Alert frontend of cognitive overload."""
    return {
        "type": "cognitive_overload_alert",
        "session_id": session_id,
        "cognitive_load": cognitive_load,
        "reasoning": reasoning,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def fatigue_rising_event(
    session_id: str, fatigue: float, trend: list[float]
) -> dict:
    """Alert frontend of rising fatigue trend."""
    return {
        "type": "fatigue_rising",
        "session_id": session_id,
        "fatigue": fatigue,
        "trend": trend,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def recovery_detected_event(
    session_id: str, stress_before: float, stress_now: float
) -> dict:
    """Notify frontend that user is recovering."""
    return {
        "type": "recovery_detected",
        "session_id": session_id,
        "stress_before": stress_before,
        "stress_now": stress_now,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def break_suggestion_event(session_id: str, reason: str) -> dict:
    """Suggest a break to the user."""
    return {
        "type": "break_suggested",
        "session_id": session_id,
        "reason": reason,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Pre-Phase 4 hardening events
# ---------------------------------------------------------------------------


def strategy_transition_event(
    session_id: str, from_mode: str, to_mode: str, reasoning: list[str]
) -> dict:
    """Emit when UX strategy mode transitions."""
    return {
        "type": "strategy_transition",
        "session_id": session_id,
        "from_mode": from_mode,
        "to_mode": to_mode,
        "reasoning": reasoning,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def adaptation_limited_event(
    session_id: str, limited_fields: list[str], guard_reason: str
) -> dict:
    """Emit when safety bounds limit an adaptation."""
    return {
        "type": "adaptation_limited",
        "session_id": session_id,
        "limited_fields": limited_fields,
        "reason": guard_reason,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def confidence_drop_event(
    session_id: str, composite_conf: float, modality_report: dict
) -> dict:
    """Emit when orchestration confidence drops below threshold."""
    return {
        "type": "confidence_drop",
        "session_id": session_id,
        "composite_confidence": composite_conf,
        "modality": modality_report,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def state_stabilized_event(
    session_id: str, stability_score: float, mode: str
) -> dict:
    """Emit when state oscillation resolves."""
    return {
        "type": "state_stabilized",
        "session_id": session_id,
        "stability_score": stability_score,
        "mode": mode,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def safety_guard_triggered_event(
    session_id: str, guard_result_dict: dict
) -> dict:
    """Emit when a safety guard fires."""
    return {
        "type": "safety_guard_triggered",
        "session_id": session_id,
        **guard_result_dict,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def orchestration_recomputed_event(
    session_id: str, trigger: str, strategy_dict: dict, confidence: float
) -> dict:
    """Emit after every orchestration recompute."""
    return {
        "type": "orchestration_recomputed",
        "session_id": session_id,
        "trigger": trigger,
        "strategy": strategy_dict,
        "confidence": confidence,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
