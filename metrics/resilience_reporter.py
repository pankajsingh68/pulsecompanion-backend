"""Resilience reporter — generates structured reports from chaos runs."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone

from utils.logger import get_logger

logger = get_logger(__name__)


class ResilienceReporter:
    """Generates structured resilience reports from chaos testing."""

    def __init__(self, reports_dir: str = "./reports") -> None:
        self.reports_dir = reports_dir

    async def generate_report(
        self, chaos_report: dict, resilience_score: float
    ) -> dict:
        """Generate a full resilience report.

        Args:
            chaos_report: ChaosReport as dict.
            resilience_score: Computed resilience score.

        Returns:
            Structured report dict. Also saves to JSON file.
        """
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "scenario": chaos_report.get("scenario_name", "unknown"),
            "duration_seconds": chaos_report.get("duration_seconds", 0),
            "resilience_score": round(resilience_score, 3),
            "events_triggered": len(chaos_report.get("events", [])),
            "recovery_validated": chaos_report.get("recovery_validated", False),
            "passed": resilience_score >= 0.6,
            "chaos_events": chaos_report.get("events", []),
        }

        # Save to file
        self._save_report(report)

        logger.info(
            "resilience_report_generated",
            scenario=report["scenario"],
            score=report["resilience_score"],
            passed=report["passed"],
        )

        return report

    def _save_report(self, report: dict) -> None:
        """Save report as JSON file."""
        os.makedirs(self.reports_dir, exist_ok=True)
        filename = f"chaos_{int(time.time())}.json"
        filepath = os.path.join(self.reports_dir, filename)
        try:
            with open(filepath, "w") as f:
                json.dump(report, f, indent=2, default=str)
            logger.info("report_saved", path=filepath)
        except Exception as e:
            logger.warning("report_save_failed", error=str(e))
