"""Adaptive sampler — adjusts sampling rate based on context.

Adjusts sampling rate based on: user state, device battery, stress level, runtime load.
"""

from __future__ import annotations

from utils.logger import get_logger

logger = get_logger(__name__)


class AdaptiveSampler:
    """Adjusts sampling rate based on user state, device battery, stress, runtime load."""

    # Default intervals by state
    INTERVALS = {
        "high_stress": 2.0,      # sample faster when stressed
        "normal": 5.0,           # default
        "low_engagement": 10.0,  # sample slower when disengaged
        "battery_low": 15.0,     # conserve battery
    }

    def compute_interval(self, state_context: dict) -> float:
        """Compute optimal sampling interval in seconds.

        Args:
            state_context: Dict with stress, engagement, battery_level, etc.

        Returns:
            Sampling interval in seconds.
        """
        stress = state_context.get("stress", 0.5)
        engagement = state_context.get("engagement", 0.5)
        battery = state_context.get("battery_level", 1.0)

        if battery < 0.2:
            return self.INTERVALS["battery_low"]
        if stress > 0.7:
            return self.INTERVALS["high_stress"]
        if engagement < 0.3:
            return self.INTERVALS["low_engagement"]
        return self.INTERVALS["normal"]
