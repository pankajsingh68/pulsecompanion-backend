"""Human state estimation via keyword-counting heuristics and optional biometric signals."""

from models.human_state import HumanState
from orchestration.router import determine_ux_mode
from utils.helpers import clamp
from utils.logger import get_logger

logger = get_logger(__name__)

STRESS_KEYWORDS: list[str] = [
    "urgent", "deadline", "overwhelmed", "anxious", "stressed",
    "panic", "help", "emergency", "stuck", "failing",
]

FOCUS_KEYWORDS: list[str] = [
    "working on", "building", "coding", "implementing",
    "designing", "creating", "need to", "trying to", "focus",
]

FATIGUE_KEYWORDS: list[str] = [
    "tired", "exhausted", "can't think", "slow",
    "brain fog", "sleepy", "drained",
]


class HeuristicStateEstimator:
    """Estimates a user's cognitive/emotional state from message text and biometrics.

    Phase 2: delegates to HumanStateEngine when USE_NEW_ENGINE is True.
    Falls back to legacy heuristic logic on any engine error.
    """

    # Set False to revert to old heuristics instantly
    USE_NEW_ENGINE = True

    def estimate_state(
        self, message: str, biometric_hint: dict | None = None
    ) -> HumanState:
        """Estimate the human state from a message and optional biometric data.

        Args:
            message: The user's text message.
            biometric_hint: Optional dict with keys "hr" (heart rate) and/or
                "hrv" (heart rate variability).

        Returns:
            A HumanState object with computed stress, focus, fatigue,
            confidence, and ux_mode values.
        """
        if self.USE_NEW_ENGINE:
            try:
                from human_state.engine import HumanStateEngine

                engine = HumanStateEngine()
                return engine.estimate_state(message, biometric_hint)
            except Exception as e:
                logger.warning("new_engine_fallback", error=str(e))
                # Falls through to existing heuristic logic below

        return self._estimate_legacy(message, biometric_hint)

    def _estimate_legacy(
        self, message: str, biometric_hint: dict | None = None
    ) -> HumanState:
        """Original heuristic estimation logic — preserved as fallback.

        Args:
            message: The user's text message.
            biometric_hint: Optional dict with keys "hr" and/or "hrv".

        Returns:
            A HumanState object with computed values.
        """
        message_lower = message.lower()

        # --- Stress estimation ---
        stress_count = sum(1 for kw in STRESS_KEYWORDS if kw in message_lower)
        stress = min(stress_count * 0.15, 1.0)

        if biometric_hint is not None:
            if biometric_hint.get("hr", 0) > 90:
                stress += 0.2
                stress = clamp(stress)
            if biometric_hint.get("hrv", 100) < 30:
                stress += 0.15
                stress = clamp(stress)

        # --- Focus estimation ---
        focus_count = sum(1 for kw in FOCUS_KEYWORDS if kw in message_lower)
        if focus_count > 0:
            focus = min(focus_count * 0.2, 1.0)
        else:
            focus = 0.5

        # --- Fatigue estimation ---
        fatigue_count = sum(1 for kw in FATIGUE_KEYWORDS if kw in message_lower)
        if fatigue_count > 0:
            fatigue = min(fatigue_count * 0.25, 1.0)
        else:
            fatigue = 0.2

        # --- Confidence estimation ---
        confidence = clamp(1.0 - (stress * 0.4 + fatigue * 0.3))

        # --- UX mode routing ---
        ux_mode = determine_ux_mode(stress, focus, fatigue)

        return HumanState(
            stress=stress,
            focus=focus,
            fatigue=fatigue,
            confidence=confidence,
            ux_mode=ux_mode,
        )
