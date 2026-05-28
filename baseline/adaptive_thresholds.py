"""Adaptive per-user thresholds for biometric interpretation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from baseline.rolling_baseline import RollingBaseline
from utils.helpers import clamp

if TYPE_CHECKING:
    from sensors.models import BiometricSnapshot


class AdaptiveThresholds:
    """Per-user adaptive thresholds for biometric interpretation.

    Replaces hardcoded values in human_state/signals/biometrics.py
    once calibrated.

    Example:
        User A: HR 90 = stress (their resting is 60)
        User B: HR 90 = normal (athlete, resting is 85)
    """

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self.hr_baseline = RollingBaseline("hr")
        self.hrv_baseline = RollingBaseline("hrv")

    def update(self, snapshot: "BiometricSnapshot") -> None:
        """Update baselines with new biometric snapshot."""
        if snapshot.hr is not None:
            self.hr_baseline.update(snapshot.hr)
        if snapshot.hrv is not None:
            self.hrv_baseline.update(snapshot.hrv)

    def hr_stress_score(self, hr: float) -> float:
        """Return stress score based on deviation from personal baseline.

        Falls back to population norms if not yet calibrated.
        """
        if not self.hr_baseline.is_calibrated():
            from human_state.signals.biometrics import BiometricSignalProcessor
            return BiometricSignalProcessor()._hr_to_stress(hr)

        deviation = self.hr_baseline.deviation(hr)
        return clamp(deviation * 1.5)

    def hrv_stress_score(self, hrv: float) -> float:
        """Return stress score based on HRV deviation from personal baseline.

        Falls back to population norms if not yet calibrated.
        """
        if not self.hrv_baseline.is_calibrated():
            from human_state.signals.biometrics import BiometricSignalProcessor
            return BiometricSignalProcessor()._hrv_to_stress(hrv)

        deviation = self.hrv_baseline.deviation(hrv)
        return clamp(-deviation * 1.5)  # negative: lower HRV = more stress
