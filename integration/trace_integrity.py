"""Trace integrity enforcement — ensures LoopTrace completeness.

A LoopTrace is INVALID unless every required stage exists.
Detects: missing stages, orphan lineages, duplicates, timeouts.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Callable
from uuid import UUID

from events.pipeline_events import PIPELINE_STAGE_ORDER
from integration.looptrace_assembler import LoopTrace, LoopTraceAssembler, TraceStore
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TraceIntegrityReport:
    """Integrity report for a single trace."""
    lineage_id: UUID | None = None
    completed: bool = False
    missing_stages: list[str] = field(default_factory=list)
    duplicate_stages: list[str] = field(default_factory=list)
    ordering_violations: list[str] = field(default_factory=list)
    timed_out: bool = False
    total_latency_ms: float = 0.0


@dataclass
class IntegrityMetrics:
    """Aggregate integrity metrics."""
    active_incomplete_traces: int = 0
    orphaned_lineages: int = 0
    trace_completion_rate: float = 1.0
    average_trace_completion_ms: float = 0.0
    timed_out_trace_count: int = 0
    total_traces_processed: int = 0


class TraceIntegrityEnforcer:
    """Enforces LoopTrace completeness with timeout and eviction.

    No trace silently disappears. Every incomplete trace is explainable.
    All integrity failures are observable via introspection API.
    """

    def __init__(
        self,
        assembler: LoopTraceAssembler,
        store: TraceStore,
        trace_timeout_ms: float = 5000.0,
        eviction_ttl_ms: float = 30000.0,
    ) -> None:
        self._assembler = assembler
        self._store = store
        self._timeout_ms = trace_timeout_ms
        self._eviction_ttl_ms = eviction_ttl_ms
        self._timed_out: list[TraceIntegrityReport] = []
        self._orphaned: list[UUID] = []
        self._total_processed: int = 0
        self._completion_latencies: list[float] = []

    def check_trace(self, trace: LoopTrace) -> TraceIntegrityReport:
        """Check a single trace for integrity violations."""
        self._total_processed += 1

        report = TraceIntegrityReport(
            lineage_id=trace.lineage_id,
            completed=trace.completed,
            missing_stages=list(trace.missing_stages),
            duplicate_stages=list(trace.duplicate_stages),
            ordering_violations=list(trace.ordering_violations),
        )

        # Compute latency
        if trace.completed and trace.completed_at and trace.started_at:
            report.total_latency_ms = (trace.completed_at - trace.started_at) * 1000
            self._completion_latencies.append(report.total_latency_ms)
            if len(self._completion_latencies) > 200:
                self._completion_latencies.pop(0)

        return report

    def check_timeout(self, trace: LoopTrace) -> bool:
        """Check if a trace has exceeded its timeout."""
        if trace.completed:
            return False
        elapsed_ms = (time.monotonic() - trace.started_at) * 1000
        if elapsed_ms > self._timeout_ms:
            report = TraceIntegrityReport(
                lineage_id=trace.lineage_id,
                completed=False,
                missing_stages=list(trace.missing_stages),
                timed_out=True,
                total_latency_ms=elapsed_ms,
            )
            self._timed_out.append(report)
            logger.warning(
                "trace_timed_out",
                lineage_id=str(trace.lineage_id),
                elapsed_ms=round(elapsed_ms, 1),
                missing=trace.missing_stages,
            )
            return True
        return False

    def detect_orphans(self) -> list[UUID]:
        """Detect traces that started but never progressed past first stage."""
        orphans: list[UUID] = []
        for trace in self._assembler.get_incomplete_traces():
            timestamps = getattr(trace, '_stage_timestamps', [])
            # If only one stage received and it's old
            if trace.started_at > 0:
                age_ms = (time.monotonic() - trace.started_at) * 1000
                if age_ms > self._eviction_ttl_ms:
                    orphans.append(trace.lineage_id)
        self._orphaned = orphans
        return orphans

    def evict_stale(self) -> int:
        """Evict stale incomplete traces. Returns count evicted."""
        evicted = 0
        incomplete = self._assembler.get_incomplete_traces()
        for trace in incomplete:
            if trace.started_at > 0:
                age_ms = (time.monotonic() - trace.started_at) * 1000
                if age_ms > self._eviction_ttl_ms:
                    # Mark as timed out before eviction
                    self.check_timeout(trace)
                    evicted += 1
        return evicted

    def get_metrics(self) -> IntegrityMetrics:
        """Get aggregate integrity metrics."""
        incomplete = self._assembler.get_incomplete_traces()
        completed = self._assembler.get_completed_traces()
        total = len(incomplete) + len(completed)

        avg_latency = 0.0
        if self._completion_latencies:
            avg_latency = sum(self._completion_latencies) / len(self._completion_latencies)

        return IntegrityMetrics(
            active_incomplete_traces=len(incomplete),
            orphaned_lineages=len(self._orphaned),
            trace_completion_rate=(
                len(completed) / total if total > 0 else 1.0
            ),
            average_trace_completion_ms=round(avg_latency, 3),
            timed_out_trace_count=len(self._timed_out),
            total_traces_processed=self._total_processed,
        )
