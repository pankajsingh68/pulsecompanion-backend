"""Subsystem integration — injects event bus into each subsystem.

Each subsystem emits its own events at its own runtime boundary.
InstrumentedIngestionPipeline becomes orchestration glue only.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from events.runtime_emitters import (
    DegradedModeEmitter,
    MemoryEmitter,
    OrchestrationEmitter,
    SafetyEmitter,
    SensorEmitter,
    StateEmitter,
    WebSocketEmitter,
)
from utils.logger import get_logger

if TYPE_CHECKING:
    from events.event_bus import AsyncEventBus

logger = get_logger(__name__)


class SubsystemEventIntegration:
    """Wires event bus into all subsystems for runtime-native emission.

    Each subsystem receives its own emitter instance.
    Emission failure never crashes the subsystem.
    """

    def __init__(self, bus: "AsyncEventBus") -> None:
        self.bus = bus
        self.sensor = SensorEmitter(bus)
        self.state = StateEmitter(bus)
        self.orchestration = OrchestrationEmitter(bus)
        self.safety = SafetyEmitter(bus)
        self.websocket = WebSocketEmitter(bus)
        self.memory = MemoryEmitter(bus)
        self.degraded = DegradedModeEmitter(bus)

        logger.info(
            "subsystem_event_integration_initialized",
            emitter_count=7,
        )
