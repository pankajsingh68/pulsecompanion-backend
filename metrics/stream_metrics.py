"""Stream metrics — packets/sec, dropouts, corruption, late packets, gaps."""

from __future__ import annotations


class StreamMetrics:
    """Collects stream-level metrics per session."""

    def __init__(self) -> None:
        self._packets: dict[str, int] = {}
        self._dropouts: dict[str, int] = {}
        self._corruptions: dict[str, int] = {}
        self._late_packets: dict[str, int] = {}
        self._gaps: dict[str, int] = {}

    def record_packet(self, session_id: str) -> None:
        self._packets[session_id] = self._packets.get(session_id, 0) + 1

    def record_dropout(self, session_id: str) -> None:
        self._dropouts[session_id] = self._dropouts.get(session_id, 0) + 1

    def record_corruption(self, session_id: str) -> None:
        self._corruptions[session_id] = self._corruptions.get(session_id, 0) + 1

    def record_late_packet(self, session_id: str) -> None:
        self._late_packets[session_id] = self._late_packets.get(session_id, 0) + 1

    def record_gap(self, session_id: str) -> None:
        self._gaps[session_id] = self._gaps.get(session_id, 0) + 1

    def snapshot(self) -> dict:
        return {
            "total_packets": sum(self._packets.values()),
            "total_dropouts": sum(self._dropouts.values()),
            "total_corruptions": sum(self._corruptions.values()),
            "total_late": sum(self._late_packets.values()),
            "total_gaps": sum(self._gaps.values()),
        }

    def reset(self) -> None:
        self._packets.clear()
        self._dropouts.clear()
        self._corruptions.clear()
        self._late_packets.clear()
        self._gaps.clear()
