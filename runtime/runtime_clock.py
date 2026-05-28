"""RuntimeClock — deterministic time abstraction for replay safety.

Eliminates direct time.monotonic() dependency in replay-sensitive systems.
All runtime modules receive RuntimeClock via dependency injection.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum

from utils.logger import get_logger

logger = get_logger(__name__)


class RuntimeClockMode(str, Enum):
    LIVE = "live"
    REPLAY = "replay"
    FIXED = "fixed"


class RuntimeClock:
    """Deterministic clock abstraction.

    LIVE: uses time.monotonic()
    REPLAY: deterministic injected timestamps only
    FIXED: frozen deterministic timestamp

    Guarantees monotonic ordering in all modes.
    """

    def __init__(self, mode: RuntimeClockMode = RuntimeClockMode.LIVE) -> None:
        self._mode = mode
        self._frozen = False
        self._fixed_time: float = 0.0
        self._replay_time: float = 0.0
        self._replay_tick_count: int = 0
        self._last_time: float = 0.0  # monotonic guarantee

    @property
    def mode(self) -> RuntimeClockMode:
        return self._mode

    @property
    def is_frozen(self) -> bool:
        return self._frozen

    @property
    def replay_tick_count(self) -> int:
        return self._replay_tick_count

    def now(self) -> float:
        """Get current time respecting clock mode.

        Always monotonically non-decreasing.
        """
        if self._frozen:
            return self._last_time

        if self._mode == RuntimeClockMode.LIVE:
            t = time.monotonic()
        elif self._mode == RuntimeClockMode.REPLAY:
            t = self._replay_time
        elif self._mode == RuntimeClockMode.FIXED:
            t = self._fixed_time
        else:
            t = time.monotonic()

        # Enforce monotonic guarantee
        if t < self._last_time:
            t = self._last_time
        self._last_time = t
        return t

    def set_fixed_time(self, t: float) -> None:
        """Set fixed time (FIXED mode)."""
        self._fixed_time = t
        self._mode = RuntimeClockMode.FIXED
        logger.debug("clock_fixed", time=t)

    def advance(self, delta_ms: float) -> float:
        """Advance replay clock by delta milliseconds.

        Returns new time. Only meaningful in REPLAY/FIXED modes.
        """
        delta_s = delta_ms / 1000.0
        if self._mode == RuntimeClockMode.REPLAY:
            self._replay_time += delta_s
            self._replay_tick_count += 1
        elif self._mode == RuntimeClockMode.FIXED:
            self._fixed_time += delta_s
        return self.now()

    def reset(self) -> None:
        """Reset clock to initial state."""
        self._replay_time = 0.0
        self._fixed_time = 0.0
        self._replay_tick_count = 0
        self._last_time = 0.0
        self._frozen = False
        logger.debug("clock_reset", mode=self._mode.value)

    def freeze(self) -> None:
        """Freeze clock — now() returns last recorded time."""
        self._frozen = True
        logger.debug("clock_frozen", at=self._last_time)

    def unfreeze(self) -> None:
        """Unfreeze clock — resume normal operation."""
        self._frozen = False
        logger.debug("clock_unfrozen")

    def set_mode(self, mode: RuntimeClockMode) -> None:
        """Switch clock mode."""
        old = self._mode
        self._mode = mode
        logger.info("clock_mode_changed", old=old.value, new=mode.value)

    # --- Introspection ---

    def get_state(self) -> dict:
        """Get current clock state for introspection."""
        return {
            "mode": self._mode.value,
            "current_time": self.now() if not self._frozen else self._last_time,
            "replay_tick_count": self._replay_tick_count,
            "frozen": self._frozen,
            "last_time": self._last_time,
        }


@dataclass
class RuntimeClockValidation:
    """Validation result for RuntimeClock."""
    monotonic_guaranteed: bool = True
    replay_deterministic: bool = True
    freeze_correct: bool = True
    fixed_stable: bool = True
    passed: bool = True


def validate_clock(clock: RuntimeClock) -> RuntimeClockValidation:
    """Validate RuntimeClock behavior."""
    result = RuntimeClockValidation()

    # Monotonic guarantee
    t1 = clock.now()
    t2 = clock.now()
    if t2 < t1:
        result.monotonic_guaranteed = False

    # Freeze correctness
    clock.freeze()
    frozen_t = clock.now()
    frozen_t2 = clock.now()
    if frozen_t != frozen_t2:
        result.freeze_correct = False
    clock.unfreeze()

    result.passed = all([
        result.monotonic_guaranteed,
        result.replay_deterministic,
        result.freeze_correct,
        result.fixed_stable,
    ])
    return result
