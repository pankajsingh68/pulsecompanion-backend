"""Per-signal confidence estimation from reliability reports."""

from confidence.confidence_models import ModalityConfidence


class ModalityConfidenceEstimator:
    """Computes per-signal confidence from reliability reports."""

    def from_reliability_report(self, report: dict) -> ModalityConfidence:
        """Convert a reliability report to ModalityConfidence.

        Args:
            report: Dict from SignalQualityAssessor.build_reliability_report().

        Returns:
            ModalityConfidence with per-signal scores.
        """
        hr_conf = report.get("hr_confidence", 1.0)
        hrv_conf = report.get("hrv_confidence", 1.0)

        mc = ModalityConfidence(
            hr_confidence=hr_conf,
            hrv_confidence=hrv_conf,
            behavioral_confidence=1.0,
            text_confidence=1.0,
            overall=self.overall_from_modalities(
                ModalityConfidence(
                    hr_confidence=hr_conf,
                    hrv_confidence=hrv_conf,
                )
            ),
        )
        return mc

    def overall_from_modalities(self, mc: ModalityConfidence) -> float:
        """Weighted average. HR+HRV weighted 0.4 each, behavioral 0.2."""
        return (
            mc.hr_confidence * 0.4
            + mc.hrv_confidence * 0.4
            + mc.behavioral_confidence * 0.2
        )
