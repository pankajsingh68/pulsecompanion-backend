"""Pure decision rules for UX orchestration. No classes, no side effects."""

from orchestration.models import ResponseTone, VerbosityLevel
from utils.helpers import clamp

VERBOSITY_MAP: dict[str, VerbosityLevel] = {
    "overload_protection": VerbosityLevel.MINIMAL,
    "calm_minimal": VerbosityLevel.SHORT,
    "focus_mode": VerbosityLevel.NORMAL,
    "normal": VerbosityLevel.NORMAL,
}

TOKEN_MAP: dict[str, int] = {
    "overload_protection": 80,
    "calm_minimal": 180,
    "focus_mode": 320,
    "normal": 512,
}


def apply_verbosity_rule(ux_mode: str) -> VerbosityLevel:
    """Map UX mode to verbosity level."""
    return VERBOSITY_MAP.get(ux_mode, VerbosityLevel.NORMAL)


def apply_tone_rules(state: dict) -> tuple[ResponseTone, str]:
    """Determine response tone from state. Returns (tone, reason)."""
    recovery_need = state.get("recovery_need", 0)
    ux_mode = state.get("ux_mode", "normal")
    engagement = state.get("engagement", 0.5)
    stress = state.get("stress", 0)

    if recovery_need > 0.7:
        return ResponseTone.WARM, f"recovery_need at {recovery_need:.2f}"
    if ux_mode == "overload_protection":
        return ResponseTone.CALM, "overload_protection mode active"
    if ux_mode == "calm_minimal":
        return ResponseTone.CALM, "calm_minimal mode active"
    if ux_mode == "focus_mode":
        return ResponseTone.TECHNICAL, "focus_mode active"
    if engagement > 0.7 and stress < 0.3:
        return ResponseTone.ENERGETIC, f"high engagement ({engagement:.2f}), low stress"
    return ResponseTone.NEUTRAL, "default tone"


def apply_notification_rules(state: dict) -> tuple[bool, int, str]:
    """Determine notification suppression. Returns (suppress, delay_s, reason)."""
    ux_mode = state.get("ux_mode", "normal")
    focus = state.get("focus", 0.5)

    if ux_mode == "overload_protection":
        return True, 300, "overload_protection: full suppression"
    if ux_mode == "calm_minimal":
        return True, 60, "calm_minimal: reduced interruptions"
    if ux_mode == "focus_mode" and focus > 0.7:
        return True, 60, f"deep focus detected ({focus:.2f})"
    if ux_mode == "focus_mode":
        return False, 30, "focus_mode: light delay"
    return False, 0, "normal: no suppression"


def apply_cognitive_support_rules(state: dict) -> tuple[bool, bool, str]:
    """Determine cognitive support. Returns (reduction, suggest_break, reason)."""
    cognitive_load = state.get("cognitive_load", 0.5)
    recovery_need = state.get("recovery_need", 0.2)
    fatigue = state.get("fatigue", 0.2)
    stress = state.get("stress", 0.2)

    reduction = False
    suggest_break = False
    reasons = []

    if cognitive_load > 0.75:
        reduction = True
        reasons.append(f"cognitive_load at {cognitive_load:.2f}")

    if recovery_need > 0.65:
        suggest_break = True
        reasons.append(f"recovery_need at {recovery_need:.2f}")

    if fatigue > 0.7 and stress > 0.5:
        suggest_break = True
        reduction = True
        reasons.append(f"fatigue ({fatigue:.2f}) + stress ({stress:.2f})")

    reason = "; ".join(reasons) if reasons else "no cognitive support needed"
    return reduction, suggest_break, reason


def apply_pacing_rules(state: dict) -> tuple[str, str, str]:
    """Determine response pacing. Returns (pacing, animation_speed, ui_density)."""
    ux_mode = state.get("ux_mode", "normal")
    engagement = state.get("engagement", 0.5)
    stress = state.get("stress", 0.2)

    if ux_mode == "overload_protection":
        return "slow", "slow", "minimal"
    if ux_mode == "calm_minimal":
        return "slight_delay", "slow", "minimal"
    if ux_mode == "focus_mode":
        return "immediate", "normal", "normal"
    if engagement > 0.7 and stress < 0.3:
        return "immediate", "fast", "rich"
    return "immediate", "normal", "normal"


def apply_emotional_support_rules(state: dict) -> tuple[float, bool, str]:
    """Determine emotional support level. Returns (level, recovery_support, reason)."""
    recovery_need = state.get("recovery_need", 0.2)
    stress = state.get("stress", 0.2)
    stability = state.get("emotional_stability", 0.7)

    if recovery_need > 0.7:
        return 0.9, True, f"high recovery_need ({recovery_need:.2f})"
    if stress > 0.7:
        return 0.7, False, f"high stress ({stress:.2f})"
    if stability < 0.4:
        return 0.8, True, f"low emotional_stability ({stability:.2f})"
    return 0.2, False, "stable state"
