"""Sensor normalizer — converts vendor-specific formats to SensorEvent."""

from datetime import datetime, timezone

from sensors.models import BiometricSnapshot, SensorEvent, SensorSource, SensorType


class SensorNormalizer:
    """Converts vendor-specific sensor formats into SensorEvent.

    All vendor adapters call this. Business logic never sees raw SDK data.
    """

    def from_biometric_hint(
        self, hint: dict, session_id: str
    ) -> list[SensorEvent]:
        """Convert existing biometric_hint dict from ChatRequest to SensorEvents.

        Args:
            hint: Dict like {"hr": 95, "hrv": 28}.
            session_id: The session identifier.

        Returns:
            List of normalized SensorEvent objects.
        """
        events: list[SensorEvent] = []
        now = datetime.now(timezone.utc)

        if "hr" in hint:
            events.append(SensorEvent(
                sensor_type=SensorType.HEART_RATE,
                value=float(hint["hr"]),
                unit="bpm",
                timestamp=now,
                source_device=SensorSource.MANUAL,
                session_id=session_id,
            ))

        if "hrv" in hint:
            events.append(SensorEvent(
                sensor_type=SensorType.HRV,
                value=float(hint["hrv"]),
                unit="ms",
                timestamp=now,
                source_device=SensorSource.MANUAL,
                session_id=session_id,
            ))

        if "gsr" in hint:
            events.append(SensorEvent(
                sensor_type=SensorType.GSR,
                value=float(hint["gsr"]),
                unit="microsiemens",
                timestamp=now,
                source_device=SensorSource.MANUAL,
                session_id=session_id,
            ))

        return events

    def to_biometric_snapshot(
        self, events: list[SensorEvent]
    ) -> BiometricSnapshot:
        """Collapse list of SensorEvents into a BiometricSnapshot."""
        snapshot = BiometricSnapshot(
            session_id=events[0].session_id if events else "",
            timestamp=datetime.now(timezone.utc),
        )

        for event in events:
            if event.sensor_type == SensorType.HEART_RATE:
                snapshot.hr = event.value
            elif event.sensor_type == SensorType.HRV:
                snapshot.hrv = event.value
            elif event.sensor_type == SensorType.GSR:
                snapshot.gsr = event.value

        return snapshot
