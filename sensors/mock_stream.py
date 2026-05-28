"""Mock biometric stream for demo/testing purposes."""

import math
import random
from datetime import datetime, timezone

from sensors.models import BiometricSnapshot, SensorSource


class MockBiometricStream:
    """Simulates a continuous wearable data stream for demos.

    Uses sine wave + noise for realistic HR/HRV variation.
    """

    def __init__(
        self,
        session_id: str,
        base_hr: float = 72,
        base_hrv: float = 45,
    ) -> None:
        self.session_id = session_id
        self.base_hr = base_hr
        self.base_hrv = base_hrv
        self._tick = 0

    async def next_snapshot(self) -> BiometricSnapshot:
        """Return next simulated biometric reading."""
        self._tick += 1

        hr = (
            self.base_hr
            + 8 * math.sin(self._tick * 0.3)
            + random.gauss(0, 2)
        )
        hrv = (
            self.base_hrv
            - 5 * math.sin(self._tick * 0.2)
            + random.gauss(0, 3)
        )

        return BiometricSnapshot(
            session_id=self.session_id,
            timestamp=datetime.now(timezone.utc),
            hr=round(max(50, min(160, hr)), 1),
            hrv=round(max(10, min(100, hrv)), 1),
            source=SensorSource.MOCK,
        )
