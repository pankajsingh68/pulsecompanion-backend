"""Device coordination — multi-device management and context handoff."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from utils.logger import get_logger

if TYPE_CHECKING:
    from websocket.manager import ConnectionManager

logger = get_logger(__name__)


class DeviceInfo:
    """Represents a connected device."""

    def __init__(self, device_id: str, device_type: str, session_id: str) -> None:
        self.device_id = device_id
        self.device_type = device_type
        self.session_id = session_id
        self.connected_at = datetime.now(timezone.utc)
        self.last_seen = datetime.now(timezone.utc)
        self.is_active = True


class DeviceRegistry:
    """Registry of all connected devices."""

    def __init__(self) -> None:
        self._devices: dict[str, DeviceInfo] = {}

    def register(self, device_id: str, device_type: str, session_id: str) -> None:
        self._devices[device_id] = DeviceInfo(device_id, device_type, session_id)

    def unregister(self, device_id: str) -> None:
        self._devices.pop(device_id, None)

    def get_session_devices(self, session_id: str) -> list[DeviceInfo]:
        return [d for d in self._devices.values() if d.session_id == session_id]

    def get_device(self, device_id: str) -> DeviceInfo | None:
        return self._devices.get(device_id)


class ActiveDeviceSelector:
    """Selects the primary device for a session."""

    def select(self, devices: list[DeviceInfo]) -> DeviceInfo | None:
        if not devices:
            return None
        # Prefer most recently seen active device
        active = [d for d in devices if d.is_active]
        if not active:
            return devices[0]
        return max(active, key=lambda d: d.last_seen)


class CrossDeviceState:
    """Maintains state that spans across devices."""

    def __init__(self) -> None:
        self._state: dict[str, dict] = {}

    def update(self, session_id: str, state: dict) -> None:
        self._state[session_id] = state

    def get(self, session_id: str) -> dict:
        return self._state.get(session_id, {})


class ContextHandoff:
    """Handles context transfer between devices."""

    async def handoff(self, from_device: str, to_device: str, context: dict) -> None:
        logger.info("context_handoff", from_device=from_device, to_device=to_device)


class DeviceCoordinator:
    """Coordinates multiple devices for a session."""

    def __init__(self, ws_manager: "ConnectionManager") -> None:
        self.ws_manager = ws_manager
        self.registry = DeviceRegistry()
        self.selector = ActiveDeviceSelector()
        self.cross_state = CrossDeviceState()
        self.handoff = ContextHandoff()

    def register_device(self, device_id: str, device_type: str, session_id: str) -> None:
        self.registry.register(device_id, device_type, session_id)
        logger.info("device_registered", device_id=device_id, session_id=session_id)

    def get_primary_device(self, session_id: str) -> DeviceInfo | None:
        devices = self.registry.get_session_devices(session_id)
        return self.selector.select(devices)
