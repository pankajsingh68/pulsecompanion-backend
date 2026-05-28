"""UX mode routing and behavioral hints for the Human State Engine."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from human_state.models import RichHumanState


def route_ux_mode(
    stress: float,
    focus: float,
    fatigue: float,
    cognitive_load: float,
    recovery_need: float,
) -> str:
    """Map state dimensions to UX mode string.

    Priority order (highest wins):
    1. overload_protection
    2. calm_minimal
    3. focus_mode
    4. normal

    Args:
        stress: Stress score [0, 1].
        focus: Focus score [0, 1].
        fatigue: Fatigue score [0, 1].
        cognitive_load: Cognitive load score [0, 1].
        recovery_need: Recovery need score [0, 1].

    Returns:
        UX mode string.
    """
    if (
        stress >= 0.8
        or (stress >= 0.6 and fatigue >= 0.6)
        or cognitive_load >= 0.85
        or recovery_need >= 0.8
    ):
        return "overload_protection"

    if stress >= 0.6 or fatigue >= 0.6 or recovery_need >= 0.6:
        return "calm_minimal"

    if focus >= 0.6 and stress < 0.5:
        return "focus_mode"

    return "normal"


def get_behavioral_hints(state: "RichHumanState") -> dict:
    """Return UX behavioral recommendations for frontend + LLM prompt.

    This is what makes PulseCompanion adaptive vs a plain chatbot.

    Args:
        state: The current RichHumanState.

    Returns:
        Dict with response_length, tone, suggest_break,
        suppress_notifications, animation_speed, ui_density.
    """
    hints = {
        "response_length": "normal",
        "tone": "balanced",
        "suggest_break": False,
        "suppress_notifications": False,
        "animation_speed": "normal",
        "ui_density": "normal",
    }

    if state.ux_mode == "overload_protection":
        hints.update({
            "response_length": "very_short",
            "tone": "calm",
            "suggest_break": True,
            "suppress_notifications": True,
            "animation_speed": "slow",
            "ui_density": "minimal",
        })
    elif state.ux_mode == "calm_minimal":
        hints.update({
            "response_length": "short",
            "tone": "calm",
            "suggest_break": state.recovery_need > 0.7,
            "suppress_notifications": True,
            "animation_speed": "slow",
            "ui_density": "minimal",
        })
    elif state.ux_mode == "focus_mode":
        hints.update({
            "response_length": "normal",
            "tone": "technical",
            "suppress_notifications": True,
            "animation_speed": "normal",
            "ui_density": "normal",
        })
    elif state.engagement > 0.7 and state.stress < 0.3:
        hints.update({
            "response_length": "detailed",
            "tone": "energetic",
            "ui_density": "rich",
        })

    return hints
