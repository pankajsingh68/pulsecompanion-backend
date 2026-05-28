"""Stability detection rules for oscillation and state variance."""

import statistics

from utils.helpers import clamp


def is_oscillating(mode_history: list[str], window: int = 4) -> bool:
    """Detect A→B→A→B oscillation in last `window` modes.

    If oscillating: force hold on current mode for next turn.
    """
    if len(mode_history) < window:
        return False

    recent = mode_history[-window:]
    # Check for alternating pattern
    if window >= 4:
        return (
            recent[0] == recent[2]
            and recent[1] == recent[3]
            and recent[0] != recent[1]
        )
    return False


def compute_stability_score(stress_trend: list[float]) -> float:
    """Compute stability score from stress trend.

    1.0 = perfectly stable, 0.0 = wildly oscillating.
    Uses stddev of last 5 stress values.
    """
    if len(stress_trend) < 2:
        return 1.0

    recent = stress_trend[-5:]
    stddev = statistics.stdev(recent)
    # Low stddev = high stability
    return clamp(1.0 - stddev * 3.0)
