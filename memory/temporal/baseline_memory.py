"""Temporal baseline memory — rolling session-level state baselines."""

from __future__ import annotations


class TemporalBaselineMemory:
    """Rolling session-level baselines for biometric + state signals."""

    def __init__(self, session_id: str, alpha: float = 0.15) -> None:
        self.session_id = session_id
        self.alpha = alpha
        self._baselines: dict[str, float | None] = {
            "hr": None, "hrv": None,
            "fatigue": None, "engagement": None,
            "stress_peak": 0.0, "recovery_rate": 0.0,
        }
        self._update_count: int = 0
        self._stress_history: list[float] = []

    def update(
        self, human_state: dict, biometric_hint: dict | None = None
    ) -> None:
        """Update baselines with new state data."""
        self._update_count += 1
        stress = human_state.get("stress", 0)
        fatigue = human_state.get("fatigue", 0)
        engagement = human_state.get("engagement", 0.5)

        self._ema_update("fatigue", fatigue)
        self._ema_update("engagement", engagement)

        if biometric_hint:
            if "hr" in biometric_hint:
                self._ema_update("hr", biometric_hint["hr"])
            if "hrv" in biometric_hint:
                self._ema_update("hrv", biometric_hint["hrv"])

        # Track stress peak and recovery rate
        self._stress_history.append(stress)
        if len(self._stress_history) > 20:
            self._stress_history.pop(0)

        if stress > (self._baselines.get("stress_peak") or 0):
            self._baselines["stress_peak"] = stress

        if len(self._stress_history) >= 3:
            recent = self._stress_history[-3:]
            if recent[0] > recent[-1]:
                self._baselines["recovery_rate"] = (recent[0] - recent[-1]) / 3.0

    def _ema_update(self, key: str, value: float) -> None:
        if self._baselines[key] is None:
            self._baselines[key] = value
        else:
            self._baselines[key] = (
                self.alpha * value + (1 - self.alpha) * self._baselines[key]
            )

    def get_summary(self) -> dict:
        return {
            "session_id": self.session_id,
            "update_count": self._update_count,
            "baselines": {
                k: round(v, 3) if v is not None else None
                for k, v in self._baselines.items()
            },
            "is_calibrated": self._update_count >= 8,
            "fatigue_trend": self._fatigue_trend(),
        }

    def _fatigue_trend(self) -> str:
        if self._update_count < 5:
            return "insufficient_data"
        fatigue = self._baselines.get("fatigue")
        if fatigue and fatigue > 0.6:
            return "accumulating"
        if fatigue and fatigue < 0.3:
            return "low"
        return "moderate"

    def get_context_string(self) -> str:
        s = self.get_summary()
        b = s["baselines"]
        return (
            f"Session baselines — "
            f"fatigue trend: {s['fatigue_trend']}, "
            f"avg fatigue: {b.get('fatigue', 'unknown')}, "
            f"avg engagement: {b.get('engagement', 'unknown')}, "
            f"stress peak: {b.get('stress_peak', 0):.2f}, "
            f"recovery rate: {b.get('recovery_rate', 0):.2f}"
        )
