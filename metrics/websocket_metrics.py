"""WebSocket metrics — events/sec, queue depth, drops, throttle activations."""

from __future__ import annotations


class WebSocketMetrics:
    """Collects WebSocket-level metrics."""

    def __init__(self) -> None:
        self._events_in: int = 0
        self._events_out: int = 0
        self._dropped: int = 0
        self._throttle_activations: int = 0
        self._reconnects: int = 0

    def record_event_in(self) -> None:
        self._events_in += 1

    def record_event_out(self) -> None:
        self._events_out += 1

    def record_drop(self) -> None:
        self._dropped += 1

    def record_throttle(self) -> None:
        self._throttle_activations += 1

    def record_reconnect(self) -> None:
        self._reconnects += 1

    def snapshot(self) -> dict:
        return {
            "events_in": self._events_in,
            "events_out": self._events_out,
            "dropped": self._dropped,
            "throttle_activations": self._throttle_activations,
            "reconnects": self._reconnects,
        }

    def reset(self) -> None:
        self._events_in = 0
        self._events_out = 0
        self._dropped = 0
        self._throttle_activations = 0
        self._reconnects = 0
