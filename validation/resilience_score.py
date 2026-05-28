"""Resilience score — composite metric from weighted sub-scores."""

from __future__ import annotations

from utils.helpers import clamp


class ResilienceScorer:
    """Computes composite resilience score (0.0–1.0) from weighted sub-scores.

    Components:
    - Stability (25%): State oscillation frequency
    - Recovery speed (25%): Mean time to recovery after chaos
    - Degradation handling (20%): Fallback activation correctness
    - Orchestration stability (20%): Strategy transition bounded-ness
    - WebSocket resilience (10%): Throttle activation speed
    """

    WEIGHTS = {
        "stability": 0.25,
        "recovery_speed": 0.25,
        "degradation_handling": 0.20,
        "orchestration_stability": 0.20,
        "websocket_resilience": 0.10,
    }

    def compute(
        self,
        stability: float,
        recovery_speed: float,
        degradation_handling: float,
        orchestration_stability: float,
        websocket_resilience: float,
    ) -> float:
        """Compute weighted composite resilience score."""
        raw = (
            stability * self.WEIGHTS["stability"]
            + recovery_speed * self.WEIGHTS["recovery_speed"]
            + degradation_handling * self.WEIGHTS["degradation_handling"]
            + orchestration_stability * self.WEIGHTS["orchestration_stability"]
            + websocket_resilience * self.WEIGHTS["websocket_resilience"]
        )
        return clamp(raw)

    def from_chaos_report(self, report: dict) -> float:
        """Compute resilience from a ChaosReport dict."""
        return report.get("resilience_score", 0.5)
