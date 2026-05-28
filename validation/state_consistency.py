"""State consistency — rules engine for detecting impossible state combinations."""

from __future__ import annotations

from utils.logger import get_logger

logger = get_logger(__name__)


# Rules: (condition_a_fn, condition_b_fn, description)
# Flags if BOTH conditions are true simultaneously
CONSISTENCY_RULES = [
    (lambda s: s.get("focus", 0) > 0.8, lambda s: s.get("stress", 0) > 0.8,
     "high_focus AND high_stress: contradictory"),
    (lambda s: s.get("trend") == "recovery", lambda s: s.get("stress", 0) > 0.7,
     "recovery trend AND high stress: inconsistent"),
    (lambda s: s.get("ux_mode") == "overload_protection", lambda s: s.get("engagement", 0) > 0.8,
     "overload_protection AND high engagement: contradictory"),
    (lambda s: s.get("fatigue", 0) < 0.2, lambda s: s.get("recovery_need", 0) > 0.8,
     "low fatigue AND high recovery_need: inconsistent"),
]


class StateConsistencyChecker:
    """Checks state for impossible/contradictory combinations."""

    def check(self, state: dict) -> list[str]:
        """Return list of violated consistency rules."""
        violations: list[str] = []
        for cond_a, cond_b, description in CONSISTENCY_RULES:
            try:
                if cond_a(state) and cond_b(state):
                    violations.append(description)
            except Exception:
                pass
        if violations:
            logger.warning("state_consistency_violations", count=len(violations))
        return violations
