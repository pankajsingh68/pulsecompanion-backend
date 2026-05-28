"""Concurrency ownership model — prevents unsafe concurrent mutation.

Defines ownership rules: single owner per mutable runtime structure.
Tracks mutations, detects violations, maintains audit trail.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class RuntimeMutationRecord:
    """Record of a single runtime mutation."""
    subsystem: str
    mutation_type: str
    timestamp: float = field(default_factory=time.monotonic)
    resource: str = ""
    success: bool = True
    replay_order: int = 0


@dataclass
class OwnershipEntry:
    """Ownership record for a runtime resource."""
    resource: str
    owner: str
    acquired_at: float = field(default_factory=time.monotonic)
    mutation_count: int = 0


@dataclass
class ConcurrencyViolation:
    """Detected concurrency violation."""
    resource: str
    attempted_by: str
    owned_by: str
    violation_type: str
    timestamp: float = field(default_factory=time.monotonic)


class RuntimeOwnershipModel:
    """Enforces single-owner mutation model for runtime state.

    Prevents unsafe concurrent mutation of shared structures.
    Maintains deterministic mutation ordering for replay.
    """

    def __init__(self) -> None:
        self._ownership: dict[str, OwnershipEntry] = {}
        self._mutations: list[RuntimeMutationRecord] = []
        self._violations: list[ConcurrencyViolation] = []
        self._mutation_counter: int = 0
        self._max_history = 500

    def claim_ownership(self, resource: str, owner: str) -> bool:
        """Claim ownership of a resource. Returns False if already owned."""
        existing = self._ownership.get(resource)
        if existing and existing.owner != owner:
            violation = ConcurrencyViolation(
                resource=resource,
                attempted_by=owner,
                owned_by=existing.owner,
                violation_type="ownership_conflict",
            )
            self._violations.append(violation)
            logger.warning(
                "ownership_conflict",
                resource=resource, attempted_by=owner, owned_by=existing.owner,
            )
            return False

        self._ownership[resource] = OwnershipEntry(resource=resource, owner=owner)
        return True

    def release_ownership(self, resource: str, owner: str) -> bool:
        """Release ownership. Only the owner can release."""
        existing = self._ownership.get(resource)
        if not existing:
            return True
        if existing.owner != owner:
            return False
        del self._ownership[resource]
        return True

    def record_mutation(
        self, subsystem: str, mutation_type: str, resource: str, success: bool = True
    ) -> RuntimeMutationRecord:
        """Record a mutation with replay-safe ordering."""
        self._mutation_counter += 1
        record = RuntimeMutationRecord(
            subsystem=subsystem,
            mutation_type=mutation_type,
            resource=resource,
            success=success,
            replay_order=self._mutation_counter,
        )
        self._mutations.append(record)
        if len(self._mutations) > self._max_history:
            self._mutations.pop(0)

        # Update ownership mutation count
        entry = self._ownership.get(resource)
        if entry:
            entry.mutation_count += 1

        return record

    def validate_mutation(self, resource: str, subsystem: str) -> bool:
        """Check if subsystem is allowed to mutate resource."""
        entry = self._ownership.get(resource)
        if entry is None:
            return True  # unclaimed resources are open
        if entry.owner != subsystem:
            self._violations.append(ConcurrencyViolation(
                resource=resource,
                attempted_by=subsystem,
                owned_by=entry.owner,
                violation_type="unauthorized_mutation",
            ))
            logger.warning(
                "unauthorized_mutation",
                resource=resource, by=subsystem, owner=entry.owner,
            )
            return False
        return True

    # --- Introspection ---

    async def get_ownership_map(self) -> dict:
        """Get current ownership map."""
        return {
            res: {"owner": entry.owner, "mutations": entry.mutation_count}
            for res, entry in self._ownership.items()
        }

    async def get_recent_mutations(self, n: int = 20) -> list[dict]:
        """Get recent mutation records."""
        return [
            {
                "subsystem": m.subsystem,
                "type": m.mutation_type,
                "resource": m.resource,
                "success": m.success,
                "order": m.replay_order,
            }
            for m in self._mutations[-n:]
        ]

    async def get_concurrency_violations(self) -> list[dict]:
        """Get all detected violations."""
        return [
            {
                "resource": v.resource,
                "attempted_by": v.attempted_by,
                "owned_by": v.owned_by,
                "type": v.violation_type,
            }
            for v in self._violations
        ]

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    @property
    def total_mutations(self) -> int:
        return self._mutation_counter
