"""Async event bus — pure pub/sub with no external broker.

No blocking I/O, no threads, no external dependencies.
Subscribers receive events asynchronously via registered callbacks.
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Coroutine

from utils.logger import get_logger

logger = get_logger(__name__)


class AsyncEventBus:
    """Lightweight async pub/sub event bus.

    Usage:
        bus = AsyncEventBus()
        bus.subscribe("sensor.ingested", my_handler)
        await bus.emit("sensor.ingested", event_payload)
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[Callable]] = {}
        self._emit_count: int = 0

    def subscribe(
        self, event_type: str, callback: Callable[..., Coroutine]
    ) -> None:
        """Register an async listener for an event type.

        Args:
            event_type: The event type string to listen for.
            callback: Async callable that receives the event payload.
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)
        logger.debug(
            "event_bus_subscribed",
            event_type=event_type,
            subscriber_count=len(self._subscribers[event_type]),
        )

    def unsubscribe(
        self, event_type: str, callback: Callable[..., Coroutine]
    ) -> None:
        """Remove a listener for an event type."""
        if event_type in self._subscribers:
            self._subscribers[event_type] = [
                cb for cb in self._subscribers[event_type] if cb is not callback
            ]

    async def emit(self, event_type: str, payload: Any) -> int:
        """Broadcast an event to all subscribers of that type.

        Args:
            event_type: The event type being emitted.
            payload: The event payload (typically a BaseEvent subclass).

        Returns:
            Number of subscribers notified.
        """
        self._emit_count += 1
        subscribers = self._subscribers.get(event_type, [])

        if not subscribers:
            return 0

        notified = 0
        for callback in subscribers:
            try:
                await callback(payload)
                notified += 1
            except Exception as e:
                logger.error(
                    "event_bus_handler_error",
                    event_type=event_type,
                    error=str(e),
                )

        return notified

    def subscriber_count(self, event_type: str) -> int:
        """Get number of subscribers for an event type."""
        return len(self._subscribers.get(event_type, []))

    @property
    def total_emitted(self) -> int:
        """Total events emitted since creation."""
        return self._emit_count

    @property
    def registered_types(self) -> list[str]:
        """All event types with at least one subscriber."""
        return [k for k, v in self._subscribers.items() if v]

    def reset(self) -> None:
        """Clear all subscriptions. Used in testing only."""
        self._subscribers.clear()
        self._emit_count = 0
