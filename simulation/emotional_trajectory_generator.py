"""Emotional trajectory generator — produces time-series emotional patterns."""

from __future__ import annotations

import asyncio
import math
import random
import time
from typing import AsyncIterator

from simulation.simulation_models import EmotionalTrajectory
from utils.logger import get_logger

logger = get_logger(__name__)


class EmotionalTrajectoryGenerator:
    """Generates emotional trajectory time-series for simulation."""

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)
        self._stop_event = asyncio.Event()

    async def generate(
        self, trajectory: EmotionalTrajectory
    ) -> AsyncIterator[dict]:
        """Generate emotional state modifiers over time.

        Yields dicts with: timestamp, state_label, intensity,
        hr_modifier, hrv_modifier, gsr_modifier.
        """
        pattern = trajectory.pattern
        duration = trajectory.duration_seconds
        intensity = trajectory.intensity
        start = time.time()

        try:
            while not self._stop_event.is_set():
                elapsed = time.time() - start
                if elapsed >= duration:
                    break

                progress = elapsed / duration  # 0.0 → 1.0
                modifiers = self._compute_modifiers(pattern, progress, intensity)

                yield {
                    "timestamp": time.time(),
                    "state_label": pattern,
                    "intensity": intensity * modifiers["intensity_curve"],
                    "hr_modifier": modifiers["hr"],
                    "hrv_modifier": modifiers["hrv"],
                    "gsr_modifier": modifiers["gsr"],
                    "progress": progress,
                }
                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            logger.info("trajectory_generator_cancelled", pattern=pattern)
            raise

    def _compute_modifiers(
        self, pattern: str, progress: float, intensity: float
    ) -> dict:
        """Compute biometric modifiers for a given pattern and progress."""
        if pattern == "burnout":
            # Slow linear degradation
            return {
                "hr": 15.0 * progress * intensity,
                "hrv": -20.0 * progress * intensity,
                "gsr": 3.0 * progress * intensity,
                "intensity_curve": progress,
            }
        elif pattern == "recovery":
            # Exponential recovery
            decay = math.exp(-3.0 * progress)
            return {
                "hr": 20.0 * decay * intensity,
                "hrv": -15.0 * decay * intensity,
                "gsr": 2.0 * decay * intensity,
                "intensity_curve": 1.0 - progress,
            }
        elif pattern == "focus":
            # Stable with micro-spikes (Poisson-like)
            spike = 1.0 if self._rng.random() < 0.05 else 0.0
            return {
                "hr": 5.0 * spike * intensity,
                "hrv": 5.0 * (1.0 - spike) * intensity,
                "gsr": -0.5 * intensity,
                "intensity_curve": 0.3 + 0.1 * spike,
            }
        elif pattern == "anxiety_spike":
            # Rapid onset, sustained peak, gradual decline
            if progress < 0.1:
                curve = progress / 0.1  # ramp up
            elif progress < 0.6:
                curve = 1.0  # sustained
            else:
                curve = 1.0 - (progress - 0.6) / 0.4  # decline
            return {
                "hr": 30.0 * curve * intensity,
                "hrv": -25.0 * curve * intensity,
                "gsr": 5.0 * curve * intensity,
                "intensity_curve": curve,
            }
        else:  # calm
            # Minimal variance, slow breathing modulation
            breath = math.sin(progress * math.pi * 12)  # ~6 breaths/min
            return {
                "hr": 2.0 * breath * intensity,
                "hrv": 3.0 * (1.0 + 0.1 * breath) * intensity,
                "gsr": -0.2 * intensity,
                "intensity_curve": 0.1,
            }

    def stop(self) -> None:
        self._stop_event.set()
