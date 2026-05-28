"""Subscription registry and lifecycle management for the event bus."""

from __future__ import annotations

from typing import Callable, Coroutine, TYPE_CHECKING

from events.pipeline_events import PIPELINE_STAGE_ORDER
from utils.logger import get_logger

if TYPE_CHECKING:
    from events.event_bus import AsyncEventBus

logger = get_logger(__name__)


class SubscriptionRegistry:
    """Manages event bus subscriptions with lifecycle control.

    Provides:
    - Named subscription groups (for bulk subscribe/unsubscribe)
    - Subscription health monitoring
    - Graceful teardown
    """

    def __init__(self, bus: "AsyncEventBus") -> None:
        self._bus = bus
        self._groups: dict[str, list[tuple[str, Callable]]] = {}

    def subscribe_group(
        self,
        group_name: str,
        subscriptions: list[tuple[str, Callable[..., Coroutine]]],
    ) -> None:
        """Subscribe a named group of handlers.

        Args:
            group_name: Identifier for this subscription group.
            subscriptions: List of (event_type, callback) tuples.
        """
        self._groups[group_name] = subscriptions
        for event_type, callback in subscriptions:
            self._bus.subscribe(event_type, callback)

        logger.info(
            "subscription_group_registered",
            group=group_name,
            count=len(subscriptions),
        )

    def unsubscribe_group(self, group_name: str) -> None:
        """Remove all subscriptions in a named group."""
        subscriptions = self._groups.pop(group_name, [])
        for event_type, callback in subscriptions:
            self._bus.unsubscribe(event_type, callback)

        logger.info(
            "subscription_group_removed",
            group=group_name,
            count=len(subscriptions),
        )

    def subscribe_all_pipeline_stages(
        self, callback: Callable[..., Coroutine], group_name: str = "pipeline_observer"
    ) -> None:
        """Subscribe a single callback to all pipeline stage events.

        Useful for validators that need to observe the full pipeline.
        """
        subscriptions = [(stage, callback) for stage in PIPELINE_STAGE_ORDER]
        self.subscribe_group(group_name, subscriptions)

    def get_active_groups(self) -> list[str]:
        """List all active subscription groups."""
        return list(self._groups.keys())

    def get_group_subscriptions(self, group_name: str) -> list[str]:
        """Get event types subscribed by a group."""
        return [et for et, _ in self._groups.get(group_name, [])]

    def teardown(self) -> None:
        """Remove all subscriptions from all groups."""
        for group_name in list(self._groups.keys()):
            self.unsubscribe_group(group_name)
        logger.info("subscription_registry_teardown_complete")
