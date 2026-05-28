"""Session simulator — composes all sub-simulators into a full session."""

from __future__ import annotations

import asyncio
import time
from typing import AsyncIterator, TYPE_CHECKING

from simulation.simulation_models import SimulatedSession
from simulation.sensor_simulator import SensorSimulator
from simulation.user_behavior_simulator import UserBehaviorSimulator
from simulation.wearable_simulator import WearableSimulator
from simulation.emotional_trajectory_generator import EmotionalTrajectoryGenerator
from simulation.workload_simulator import WorkloadSimulator
from utils.logger import get_logger

if TYPE_CHECKING:
    from streaming.ingestion import SensorIngestionPipeline

logger = get_logger(__name__)


class SessionSimulator:
    """Composes all sub-simulators and feeds output into ingestion pipeline."""

    def __init__(
        self,
        sensor_sim: SensorSimulator | None = None,
        behavior_sim: UserBehaviorSimulator | None = None,
        wearable_sim: WearableSimulator | None = None,
        trajectory_gen: EmotionalTrajectoryGenerator | None = None,
        workload_sim: WorkloadSimulator | None = None,
    ) -> None:
        self.sensor_sim = sensor_sim or SensorSimulator()
        self.behavior_sim = behavior_sim or UserBehaviorSimulator()
        self.wearable_sim = wearable_sim
        self.trajectory_gen = trajectory_gen or EmotionalTrajectoryGenerator()
        self.workload_sim = workload_sim or WorkloadSimulator()
        self._tasks: list[asyncio.Task] = []
        self._stop_event = asyncio.Event()

    async def run(
        self, session: SimulatedSession, ingestion_pipeline: "SensorIngestionPipeline"
    ) -> AsyncIterator[dict]:
        """Run a full simulated session, feeding into ingestion pipeline.

        Args:
            session: The session configuration.
            ingestion_pipeline: The pipeline to feed sensor data into.

        Yields:
            Event dicts as they are processed.
        """
        from sensors.models import BiometricSnapshot, SensorSource

        session_id = session.session_id
        duration = session.trajectory.duration_seconds
        start = time.time()

        logger.info(
            "session_simulation_started",
            session_id=session_id,
            pattern=session.trajectory.pattern,
            duration=duration,
        )

        try:
            async for snapshot in self.sensor_sim.stream(session_id, duration):
                if self._stop_event.is_set():
                    break

                # Convert to BiometricSnapshot for ingestion
                bio_snapshot = BiometricSnapshot(
                    session_id=session_id,
                    hr=snapshot.hr,
                    hrv=snapshot.hrv,
                    gsr=snapshot.gsr,
                    source=SensorSource.MOCK,
                )

                # Feed into pipeline
                try:
                    await ingestion_pipeline.ingest(session_id, bio_snapshot)
                except Exception as e:
                    logger.warning("ingestion_error_during_sim", error=str(e))

                yield {
                    "type": "sensor_ingested",
                    "session_id": session_id,
                    "timestamp": snapshot.timestamp,
                    "hr": snapshot.hr,
                    "hrv": snapshot.hrv,
                }
        except asyncio.CancelledError:
            logger.info("session_simulation_cancelled", session_id=session_id)
            raise

        elapsed = time.time() - start
        logger.info(
            "session_simulation_complete",
            session_id=session_id,
            elapsed_seconds=round(elapsed, 2),
        )

    async def stop(self) -> None:
        """Gracefully stop all simulation tasks."""
        self._stop_event.set()
        self.sensor_sim.stop()
        self.behavior_sim.stop()
        self.workload_sim.stop()
        if self.trajectory_gen:
            self.trajectory_gen.stop()
        if self.wearable_sim:
            self.wearable_sim.stop()

        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        logger.info("simulator_stopped", simulator="SessionSimulator")
