"""WebSocket bootstrap — connection manager and heartbeat."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from utils.logger import get_logger
from websocket.manager import ConnectionManager
from websocket.heartbeat import HeartbeatMonitor

if TYPE_CHECKING:
    from bootstrap.dependency_registry import DependencyRegistry

logger = get_logger(__name__)


@dataclass
class WebSocketBundle:
    """WebSocket infrastructure components."""
    ws_manager: ConnectionManager
    heartbeat: HeartbeatMonitor


async def bootstrap_websocket(registry: "DependencyRegistry") -> WebSocketBundle:
    """Initialize WebSocket infrastructure."""
    ws_manager = ConnectionManager()
    heartbeat = HeartbeatMonitor(ws_manager)
    await heartbeat.start()

    registry.register("ws_manager", ws_manager)
    registry.register("heartbeat", heartbeat)

    bundle = WebSocketBundle(ws_manager=ws_manager, heartbeat=heartbeat)
    logger.info("subsystem_initialized", subsystem="websocket", component_count=2)
    return bundle
