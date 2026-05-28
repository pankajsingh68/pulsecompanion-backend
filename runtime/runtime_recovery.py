"""Crash-safe runtime recovery and warm restart support.

Persists and restores: sessions, emotional continuity, degraded states,
orchestration hysteresis, stabilization history.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from utils.logger import get_logger

logger = get_logger(__name__)

SNAPSHOT_VERSION = "1.0.0"
SNAPSHOT_DIR = "./runtime_snapshots"
CURRENT_SNAPSHOT_VERSION = "1.0.0"


@dataclass
class MigrationReport:
    """Report from a snapshot migration."""
    source_version: str = ""
    target_version: str = CURRENT_SNAPSHOT_VERSION
    migrations_applied: list[str] = field(default_factory=list)
    success: bool = True
    warnings: list[str] = field(default_factory=list)


class SnapshotMigrator:
    """Migrates snapshots between schema versions.

    Migrations are deterministic, idempotent, and failure-safe.
    """

    MIGRATION_CHAIN = ["1.0.0"]  # ordered version chain

    def needs_migration(self, version: str) -> bool:
        """Check if snapshot needs migration."""
        return version != CURRENT_SNAPSHOT_VERSION

    def migrate(self, data: dict, source_version: str) -> tuple[dict, MigrationReport]:
        """Sequentially migrate snapshot to current version.

        Returns (migrated_data, report).
        """
        report = MigrationReport(source_version=source_version)
        current = source_version

        try:
            # Future migrations would be applied here sequentially:
            # if current == "0.9.0":
            #     data = self._migrate_v09_to_v10(data)
            #     report.migrations_applied.append("0.9.0 → 1.0.0")
            #     current = "1.0.0"

            data["version"] = CURRENT_SNAPSHOT_VERSION
            report.success = True
        except Exception as e:
            report.success = False
            report.warnings.append(f"migration_failed: {e}")
            logger.error("snapshot_migration_failed", error=str(e))

        return data, report


@dataclass
class RecoverySnapshot:
    """Versioned runtime state snapshot for crash recovery."""
    version: str = SNAPSHOT_VERSION
    created_at: str = ""
    runtime_version: str = "pulse_companion_v5"
    lineage_count: int = 0
    checksum: str = ""

    # Persisted state
    active_sessions: list[dict] = field(default_factory=list)
    emotional_continuity: dict[str, dict] = field(default_factory=dict)
    degraded_states: dict[str, dict] = field(default_factory=dict)
    stabilization_metrics: dict = field(default_factory=dict)
    orchestration_hysteresis: dict[str, dict] = field(default_factory=dict)
    recovery_ramps: dict[str, dict] = field(default_factory=dict)
    trace_metadata: dict = field(default_factory=dict)


@dataclass
class RecoveryMetrics:
    """Metrics from a recovery operation."""
    restore_time_ms: float = 0.0
    restored_sessions: int = 0
    corrupted_snapshots: int = 0
    recovered_traces: int = 0
    abandoned_traces: int = 0


class RecoverySerializer:
    """Deterministic serialization with corruption detection."""

    def serialize(self, snapshot: RecoverySnapshot) -> str:
        """Serialize snapshot to JSON with checksum."""
        snapshot.created_at = datetime.now(timezone.utc).isoformat()
        data = {
            "version": snapshot.version,
            "created_at": snapshot.created_at,
            "runtime_version": snapshot.runtime_version,
            "lineage_count": snapshot.lineage_count,
            "active_sessions": snapshot.active_sessions,
            "emotional_continuity": snapshot.emotional_continuity,
            "degraded_states": snapshot.degraded_states,
            "stabilization_metrics": snapshot.stabilization_metrics,
            "orchestration_hysteresis": snapshot.orchestration_hysteresis,
            "recovery_ramps": snapshot.recovery_ramps,
            "trace_metadata": snapshot.trace_metadata,
        }
        content = json.dumps(data, sort_keys=True, default=str)
        checksum = hashlib.sha256(content.encode()).hexdigest()[:16]
        data["checksum"] = checksum
        return json.dumps(data, indent=2, default=str)

    def deserialize(self, content: str) -> RecoverySnapshot | None:
        """Deserialize and validate checksum."""
        try:
            data = json.loads(content)
            stored_checksum = data.pop("checksum", "")

            # Verify checksum
            verify_content = json.dumps(data, sort_keys=True, default=str)
            expected = hashlib.sha256(verify_content.encode()).hexdigest()[:16]

            if stored_checksum != expected:
                logger.warning("snapshot_checksum_mismatch")
                return None

            return RecoverySnapshot(
                version=data.get("version", ""),
                created_at=data.get("created_at", ""),
                lineage_count=data.get("lineage_count", 0),
                active_sessions=data.get("active_sessions", []),
                emotional_continuity=data.get("emotional_continuity", {}),
                degraded_states=data.get("degraded_states", {}),
                stabilization_metrics=data.get("stabilization_metrics", {}),
                orchestration_hysteresis=data.get("orchestration_hysteresis", {}),
                recovery_ramps=data.get("recovery_ramps", {}),
                trace_metadata=data.get("trace_metadata", {}),
                checksum=stored_checksum,
            )
        except (json.JSONDecodeError, KeyError) as e:
            logger.error("snapshot_deserialize_failed", error=str(e))
            return None


class RuntimeRecoveryManager:
    """Manages crash-safe snapshots and warm restart recovery."""

    def __init__(self, snapshot_dir: str = SNAPSHOT_DIR) -> None:
        self._dir = snapshot_dir
        self._serializer = RecoverySerializer()
        self._last_snapshot: RecoverySnapshot | None = None

    def create_snapshot(
        self,
        sessions: list[dict] | None = None,
        continuity: dict[str, dict] | None = None,
        degraded: dict[str, dict] | None = None,
        stabilization: dict | None = None,
        hysteresis: dict[str, dict] | None = None,
        lineage_count: int = 0,
    ) -> RecoverySnapshot:
        """Create a runtime snapshot for persistence."""
        snapshot = RecoverySnapshot(
            lineage_count=lineage_count,
            active_sessions=sessions or [],
            emotional_continuity=continuity or {},
            degraded_states=degraded or {},
            stabilization_metrics=stabilization or {},
            orchestration_hysteresis=hysteresis or {},
        )

        # Persist atomically
        os.makedirs(self._dir, exist_ok=True)
        filepath = os.path.join(self._dir, "latest.json")
        tmp_path = filepath + ".tmp"

        content = self._serializer.serialize(snapshot)
        try:
            with open(tmp_path, "w") as f:
                f.write(content)
            os.replace(tmp_path, filepath)  # atomic on POSIX
            self._last_snapshot = snapshot
            logger.info("snapshot_created", lineage_count=lineage_count)
        except Exception as e:
            logger.error("snapshot_write_failed", error=str(e))

        return snapshot

    def restore_snapshot(self) -> tuple[RecoverySnapshot | None, RecoveryMetrics]:
        """Restore from latest snapshot. Returns (snapshot, metrics)."""
        start = time.monotonic()
        metrics = RecoveryMetrics()
        filepath = os.path.join(self._dir, "latest.json")

        if not os.path.exists(filepath):
            logger.info("no_snapshot_found")
            return None, metrics

        try:
            with open(filepath) as f:
                content = f.read()
        except Exception as e:
            logger.error("snapshot_read_failed", error=str(e))
            metrics.corrupted_snapshots += 1
            return None, metrics

        snapshot = self._serializer.deserialize(content)
        if snapshot is None:
            metrics.corrupted_snapshots += 1
            return None, metrics

        # Task 4: Apply migrations if needed
        migrator = SnapshotMigrator()
        if migrator.needs_migration(snapshot.version):
            # Re-parse raw data for migration
            raw_data = json.loads(content)
            raw_data.pop("checksum", None)
            migrated_data, migration_report = migrator.migrate(raw_data, snapshot.version)
            if migration_report.success:
                snapshot.version = CURRENT_SNAPSHOT_VERSION
                logger.info("snapshot_migrated", migrations=migration_report.migrations_applied)

        metrics.restore_time_ms = (time.monotonic() - start) * 1000
        metrics.restored_sessions = len(snapshot.active_sessions)
        self._last_snapshot = snapshot

        logger.info(
            "snapshot_restored",
            sessions=metrics.restored_sessions,
            restore_ms=round(metrics.restore_time_ms, 2),
        )
        return snapshot, metrics

    def validate_snapshot(self, snapshot: RecoverySnapshot) -> bool:
        """Validate snapshot integrity."""
        if snapshot.version != SNAPSHOT_VERSION:
            return False
        if not snapshot.created_at:
            return False
        return True

    def cleanup_old_snapshots(self, keep: int = 3) -> int:
        """Remove old snapshots, keeping the N most recent."""
        if not os.path.isdir(self._dir):
            return 0
        files = sorted(
            [f for f in os.listdir(self._dir) if f.endswith(".json")],
            key=lambda f: os.path.getmtime(os.path.join(self._dir, f)),
            reverse=True,
        )
        removed = 0
        for f in files[keep:]:
            os.remove(os.path.join(self._dir, f))
            removed += 1
        return removed
