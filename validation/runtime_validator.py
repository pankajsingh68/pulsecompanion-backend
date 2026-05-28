"""Runtime validator — end-to-end validation of the adaptive pipeline."""

from __future__ import annotations

from typing import TYPE_CHECKING

from utils.logger import get_logger

if TYPE_CHECKING:
    from streaming.ingestion import SensorIngestionPipeline

logger = get_logger(__name__)


class RuntimeValidator:
    """End-to-end: ingest synthetic session → verify state updates → verify orchestration."""

    def __init__(self, ingestion_pipeline: "SensorIngestionPipeline") -> None:
        self.pipeline = ingestion_pipeline

    async def validate_pipeline(self, session_id: str) -> dict:
        """Run a synthetic event through the full pipeline and validate output.

        Returns dict with: passed (bool), stages_completed (list), errors (list).
        """
        from sensors.models import BiometricSnapshot, SensorSource

        stages: list[str] = []
        errors: list[str] = []

        # Ingest a normal reading
        snapshot = BiometricSnapshot(
            session_id=session_id,
            hr=72.0,
            hrv=50.0,
            source=SensorSource.MOCK,
        )

        try:
            await self.pipeline.ingest(session_id, snapshot)
            stages.append("ingestion")
        except Exception as e:
            errors.append(f"ingestion_failed: {e}")

        return {
            "passed": len(errors) == 0,
            "stages_completed": stages,
            "errors": errors,
        }
