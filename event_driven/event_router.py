"""Event router — routes system events to appropriate handlers."""

from __future__ import annotations

from typing import Callable

from events.event_models import EventType, SystemEvent
from utils.logger import get_logger

logger = get_logger(__name__)


class EventRouter:
    """Routes incoming system events to appropriate handlers.

    SystemEvent.event_type → handler mapping.
    Replaces scattered if/elif chains in ingestion pipeline.
    """

    def __init__(self) -> None:
        self._handlers: dict[EventType, list[Callable]] = {}

    def register(self, event_type: EventType, handler: Callable) -> None:
        """Register a handler for an event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    async def route(self, event: SystemEvent) -> None:
        """Route an event to all registered handlers."""
        handlers = self._handlers.get(event.event_type, [])
        for handler in handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(
                    "event_handler_error",
                    event_type=event.event_type.value,
                    error=str(e),
                )
