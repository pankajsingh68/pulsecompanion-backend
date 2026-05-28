"""Global registry of session actors."""

from actors.session_actor import SessionActor
from utils.logger import get_logger

logger = get_logger(__name__)


class ActorRegistry:
    """Global registry of session actors.

    Creates actors on first message. Cleans up on session end.
    """

    def __init__(self) -> None:
        self._actors: dict[str, SessionActor] = {}

    def get_or_create(self, session_id: str) -> SessionActor:
        """Get existing actor or create a new one."""
        if session_id not in self._actors:
            self._actors[session_id] = SessionActor(session_id)
            logger.info("actor_created", session_id=session_id)
        return self._actors[session_id]

    def destroy(self, session_id: str) -> None:
        """Destroy an actor for a session."""
        self._actors.pop(session_id, None)
        logger.info("actor_destroyed", session_id=session_id)

    def list_active(self) -> list[str]:
        """List all active session IDs."""
        return list(self._actors.keys())
