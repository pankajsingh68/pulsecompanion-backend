"""Biometric signal processing — HR, HRV, GSR normalization."""

from utils.helpers import clamp


class BiometricSignalProcessor:
    """Process raw biometric values into normalized 0-1 scores.

    Handles heart rate, heart rate variability, and galvanic skin response.
    Designed for future wearable streaming integration.
    """

    # Clinical reference ranges for normalization
    HR_RESTING_LOW = 50
    HR_RESTING_HIGH = 75
    HR_ELEVATED = 90
    HR_HIGH_STRESS = 105

    HRV_HIGH = 70       # ms — low stress
    HRV_MEDIUM = 45     # ms — moderate
    HRV_LOW = 30        # ms — stressed
    HRV_VERY_LOW = 20   # ms — high stress

    def process(
        self,
        hr: float | None,
        hrv: float | None,
        gsr: float | None = None,
    ) -> dict:
        """Process biometric inputs into normalized scores.

        Args:
            hr: Heart rate in BPM, or None.
            hrv: Heart rate variability in ms, or None.
            gsr: Galvanic skin response (future), or None.

        Returns:
            Dict with keys: bio_stress, bio_fatigue, bio_stability.
            Returns empty dict if no biometric data available.
        """
        if hr is None and hrv is None and gsr is None:
            return {}

        scores: dict[str, float] = {}

        if hr is not None:
            scores["bio_stress_from_hr"] = self._hr_to_stress(hr)

        if hrv is not None:
            scores["bio_stress_from_hrv"] = self._hrv_to_stress(hrv)
            scores["bio_stability"] = self._hrv_to_stability(hrv)

        # Combine HR and HRV stress signals
        stress_signals = [v for k, v in scores.items() if "stress" in k]
        if stress_signals:
            scores["bio_stress"] = clamp(sum(stress_signals) / len(stress_signals))

        # Fatigue proxy: low HR + low HRV together suggest fatigue
        if hr is not None and hrv is not None:
            scores["bio_fatigue"] = self._estimate_fatigue(hr, hrv)

        return scores

    def _hr_to_stress(self, hr: float) -> float:
        """Map heart rate to stress score."""
        if hr <= self.HR_RESTING_HIGH:
            return 0.1
        if hr <= self.HR_ELEVATED:
            return 0.3
        if hr <= self.HR_HIGH_STRESS:
            return 0.6
        return 0.9

    def _hrv_to_stress(self, hrv: float) -> float:
        """Map HRV to stress score (lower HRV = higher stress)."""
        if hrv >= self.HRV_HIGH:
            return 0.1
        if hrv >= self.HRV_MEDIUM:
            return 0.3
        if hrv >= self.HRV_LOW:
            return 0.6
        return 0.85

    def _hrv_to_stability(self, hrv: float) -> float:
        """Map HRV to emotional stability (higher HRV = more stable)."""
        return clamp(hrv / self.HRV_HIGH)

    def _estimate_fatigue(self, hr: float, hrv: float) -> float:
        """Estimate fatigue from combined HR + HRV pattern.

        Low HR + low HRV = parasympathetic fatigue signature.
        """
        hr_range = self.HR_RESTING_HIGH - self.HR_RESTING_LOW
        if hr_range == 0:
            hr_factor = 0.5
        else:
            hr_factor = clamp(
                1.0 - (hr - self.HR_RESTING_LOW) / hr_range
            )
        hrv_factor = clamp(1.0 - hrv / self.HRV_HIGH)
        return clamp((hr_factor * 0.4) + (hrv_factor * 0.6))
