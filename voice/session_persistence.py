"""Voice session persistence — warm session handoff.

Persists emotional state at session end. Loads on next session start.
"""

from __future__ import annotations

import json
import os
from collections import deque
from dataclasses import dataclass
from uuid import UUID

from utils.logger import get_logger

logger = get_logger(__name__)

SNAPSHOT_DIR = "./voice_sessions"
MAX_SNAPSHOTS = 30
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class VoiceSessionSnapshot:
    """Persisted voice session state for warm restart."""
    session_id: str
    lineage_id: str
    final_emotional_state: dict
    final_rhythm_state: dict
    final_regulation_state: dict
    final_pattern_state: dict
    session_duration: float
    cycle_count: int
    overload_events: int
    recovery_achieved: bool
    snapshot_timestamp: float
    schema_version: int


class VoiceSessionPersistence:
    """Saves and loads voice session snapshots for warm handoff."""

    def __init__(self, snapshot_dir: str = SNAPSHOT_DIR) -> None:
        self._dir = snapshot_dir
        self._recent: deque[str] = deque(maxlen=MAX_SNAPSHOTS)

    async def save_snapshot(self, snapshot: VoiceSessionSnapshot) -> None:
        """Save session snapshot as JSON."""
        os.makedirs(self._dir, exist_ok=True)
        filepath = os.path.join(self._dir, f"{snapshot.session_id}.json")

        data = {
            "session_id": snapshot.session_id,
            "lineage_id": snapshot.lineage_id,
            "final_emotional_state": snapshot.final_emotional_state,
            "final_rhythm_state": snapshot.final_rhythm_state,
            "final_regulation_state": snapshot.final_regulation_state,
            "final_pattern_state": snapshot.final_pattern_state,
            "session_duration": snapshot.session_duration,
            "cycle_count": snapshot.cycle_count,
            "overload_events": snapshot.overload_events,
            "recovery_achieved": snapshot.recovery_achieved,
            "snapshot_timestamp": snapshot.snapshot_timestamp,
            "schema_version": snapshot.schema_version,
        }

        try:
            with open(filepath, "w") as f:
                json.dump(data, f, indent=2, default=str)
            self._recent.append(snapshot.session_id)
            self._evict_old()
            logger.info("voice_session_saved", session_id=snapshot.session_id)
        except Exception as e:
            logger.warning("voice_session_save_failed", error=str(e))

    async def load_last_snapshot(self, session_id: str) -> VoiceSessionSnapshot | None:
        """Load previous session snapshot for warm start."""
        filepath = os.path.join(self._dir, f"{session_id}.json")
        if not os.path.exists(filepath):
            return None

        try:
            with open(filepath) as f:
                data = json.load(f)
            return VoiceSessionSnapshot(
                session_id=data["session_id"],
                lineage_id=data.get("lineage_id", ""),
                final_emotional_state=data.get("final_emotional_state", {}),
                final_rhythm_state=data.get("final_rhythm_state", {}),
                final_regulation_state=data.get("final_regulation_state", {}),
                final_pattern_state=data.get("final_pattern_state", {}),
                session_duration=data.get("session_duration", 0),
                cycle_count=data.get("cycle_count", 0),
                overload_events=data.get("overload_events", 0),
                recovery_achieved=data.get("recovery_achieved", False),
                snapshot_timestamp=data.get("snapshot_timestamp", 0),
                schema_version=data.get("schema_version", 1),
            )
        except Exception as e:
            logger.warning("voice_session_load_failed", session_id=session_id, error=str(e))
            return None

    async def list_recent_sessions(self, limit: int = 10) -> list[str]:
        """List recent session IDs."""
        return list(self._recent)[-limit:]

    def _evict_old(self) -> None:
        """Evict oldest snapshots beyond MAX_SNAPSHOTS."""
        if not os.path.isdir(self._dir):
            return
        files = sorted(
            [f for f in os.listdir(self._dir) if f.endswith(".json")],
            key=lambda f: os.path.getmtime(os.path.join(self._dir, f)),
        )
        while len(files) > MAX_SNAPSHOTS:
            oldest = files.pop(0)
            try:
                os.remove(os.path.join(self._dir, oldest))
            except Exception:
                pass
