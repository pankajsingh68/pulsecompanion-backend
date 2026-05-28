"""Actor runtime — wires registry + dispatcher, exposes send_to_session()."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from actors.actor_registry import ActorRegistry
    from actors.actor_models import ActorMessage


class ActorRuntime:
    """Wires actor registry with dispatcher. Exposes send_to_session()."""

    def __init__(self, registry: "ActorRegistry") -> None:
        self.registry = registry

    async def send_to_session(
        self, session_id: str, message: "ActorMessage"
    ) -> None:
        """Send a message to a session's actor."""
        actor = self.registry.get_or_create(session_id)
        await actor.send(message)
