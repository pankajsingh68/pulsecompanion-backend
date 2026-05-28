"""Signal quality assessment — estimates reliability of sensor readings."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sensors.models import BiometricSnapshot


class SignalQualityAssessor:
    """Estimates reliability of each incoming sensor reading.

    Noisy/missing signals get lower confidence weights in fusion.
    """

    def assess_hr(self, hr: float | None, prev_hr: float | None = None) -> float:
        """Return confidence 0.0-1.0 for HR reading.

        Rules:
        - None → 0.0
        - Outside physiological range (30-220 BPM) → 0.1
        - Delta from prev > 40 BPM in one tick → 0.3 (spike artifact)
        - Normal → 1.0
        """
        if hr is None:
            return 0.0
        if hr < 30 or hr > 220:
            return 0.1
        if prev_hr is not None and abs(hr - prev_hr) > 40:
            return 0.3
        return 1.0

    def assess_hrv(self, hrv: float | None) -> float:
        """Return confidence 0.0-1.0 for HRV reading."""
        if hrv is None:
            return 0.0
        if hrv < 5 or hrv > 200:
            return 0.1
        return 1.0

    def build_reliability_report(
        self,
        snapshot: "BiometricSnapshot",
        prev_snapshot: "BiometricSnapshot | None" = None,
    ) -> dict:
        """Build a full reliability report for a biometric snapshot.

        Args:
            snapshot: Current biometric readings.
            prev_snapshot: Previous readings for delta checks.

        Returns:
            Dict with hr_confidence, hrv_confidence, overall_confidence, warnings.
        """
        prev_hr = prev_snapshot.hr if prev_snapshot else None

        return {
            "hr_confidence": self.assess_hr(snapshot.hr, prev_hr),
            "hrv_confidence": self.assess_hrv(snapshot.hrv),
            "overall_confidence": self._overall(snapshot, prev_snapshot),
            "warnings": self._build_warnings(snapshot, prev_snapshot),
        }

    def _overall(
        self,
        snap: "BiometricSnapshot",
        prev: "BiometricSnapshot | None",
    ) -> float:
        """Compute overall confidence from individual scores."""
        scores = [
            self.assess_hr(snap.hr, prev.hr if prev else None),
            self.assess_hrv(snap.hrv),
        ]
        valid = [s for s in scores if s > 0]
        return sum(valid) / len(valid) if valid else 0.0

    def _build_warnings(
        self,
        snap: "BiometricSnapshot",
        prev: "BiometricSnapshot | None",
    ) -> list[str]:
        """Build list of warning strings for problematic readings."""
        warnings: list[str] = []

        if snap.hr is None:
            warnings.append("hr_missing")
        elif snap.hr < 30 or snap.hr > 220:
            warnings.append("hr_out_of_range")

        if snap.hrv is None:
            warnings.append("hrv_missing")

        if prev and snap.hr and prev.hr and abs(snap.hr - prev.hr) > 40:
            warnings.append("hr_spike_detected")

        return warnings
