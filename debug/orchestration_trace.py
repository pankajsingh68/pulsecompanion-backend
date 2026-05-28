"""Orchestration trace — full audit trail for decisions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from utils.logger import get_logger

if TYPE_CHECKING:
    from confidence.confidence_models import OrchestrationConfidence
    from event_driven.event_models import OrchestrationRequest
    from orchestration.models import UXStrategy
    from safety.safety_models import SafetyGuardResult

logger = get_logger(__name__)


class OrchestrationTrace:
    """Full audit trail for one orchestration decision.

    Records: inputs → rule outputs → confidence → safety → final strategy.
    Used for: debugging why a specific decision was made.
    """

    def __init__(self) -> None:
        self._traces: dict[str, list[dict]] = {}

    def record(
        self,
        session_id: str,
        request: "OrchestrationRequest",
        rule_outputs: dict,
        conf: "OrchestrationConfidence",
        guard_result: "SafetyGuardResult",
        final_strategy: "UXStrategy",
    ) -> None:
        """Record a full orchestration trace."""
        if session_id not in self._traces:
            self._traces[session_id] = []

        self._traces[session_id].append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trigger": request.trigger.value,
            "human_state": request.human_state,
            "rule_outputs": rule_outputs,
            "confidence": conf.model_dump(),
            "guard_result": guard_result.model_dump(),
            "final_strategy_mode": final_strategy.ux_mode,
            "final_reasoning": final_strategy.reasoning,
        })

        # Keep max 50 traces per session
        if len(self._traces[session_id]) > 50:
            self._traces[session_id].pop(0)

    def get_trace(
        self, session_id: str, strategy_timestamp: datetime | None = None
    ) -> dict | None:
        """Get a trace by session and optional timestamp."""
        traces = self._traces.get(session_id, [])
        if not traces:
            return None
        if strategy_timestamp is None:
            return traces[-1]
        # Find closest trace
        target = strategy_timestamp.isoformat()
        for trace in reversed(traces):
            if trace["timestamp"] <= target:
                return trace
        return traces[0] if traces else None
