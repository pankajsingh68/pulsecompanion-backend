"""UX mode routing based on human state scores."""

from orchestration.modes import UXMode


def determine_ux_mode(stress: float, focus: float, fatigue: float) -> str:
    """Determine the appropriate UX mode based on state scores.

    Priority order: OVERLOAD_PROTECTION > CALM_MINIMAL > FOCUS_MODE > NORMAL.

    Args:
        stress: Stress score in [0.0, 1.0].
        focus: Focus score in [0.0, 1.0].
        fatigue: Fatigue score in [0.0, 1.0].

    Returns:
        A UX mode string constant.
    """
    if stress >= 0.8 or (stress >= 0.6 and fatigue >= 0.6):
        return UXMode.OVERLOAD_PROTECTION
    if stress >= 0.6 or fatigue >= 0.6:
        return UXMode.CALM_MINIMAL
    if focus >= 0.6 and stress < 0.5:
        return UXMode.FOCUS_MODE
    return UXMode.NORMAL
