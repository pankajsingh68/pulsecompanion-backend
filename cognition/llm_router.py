"""LLM Router — selects backend based on emotional state and health.

Deterministic routing. No random selection. Model-agnostic.
The emotional runtime decides HOW the model behaves.
The router decides WHICH model to use.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any

from cognition.llm_health_monitor import LLMHealthMonitor
from cognition.response_policy_engine import ResponsePolicy
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class RoutingDecision:
    """Result of routing decision."""
    selected_backend: str
    reason: str
    fallback_used: bool = False


class LLMRouter:
    """Selects the correct LLM backend based on emotional/runtime state.

    Routing is deterministic: same inputs → same backend selection.
    Future-compatible for Claude, Mistral, Llama 3, Gemma.
    """

    def __init__(
        self,
        backends: dict[str, Any] | None = None,
        health_monitor: LLMHealthMonitor | None = None,
    ) -> None:
        self._backends = backends or {}
        self._health = health_monitor or LLMHealthMonitor()
        self._routing_history: deque[RoutingDecision] = deque(maxlen=100)
        self._default_backend = "phi3_ollama"

        # Register all backends with health monitor
        for name in self._backends:
            self._health.register_backend(name)

    def register_backend(self, name: str, backend: Any) -> None:
        """Register a new backend."""
        self._backends[name] = backend
        self._health.register_backend(name)

    def select_backend(
        self,
        policy: ResponsePolicy,
        emotional_state: dict | None = None,
    ) -> tuple[Any | None, RoutingDecision]:
        """Select the appropriate backend.

        Returns (backend_instance, routing_decision).
        Returns (None, decision) if no healthy backend available.
        """
        emotional_state = emotional_state or {}
        cognitive_load = emotional_state.get("cognitive_load", 0.5)
        overload = emotional_state.get("overload_detected", False)

        # Rule 1: Fast grounding states → Phi3
        if (policy.response_mode in ("minimal", "grounding")
                or cognitive_load > 0.75
                or overload):
            target = "phi3_ollama"
            reason = f"fast_grounding: mode={policy.response_mode}, cog_load={cognitive_load:.2f}"

        # Rule 2: Reflective/supportive (future: larger model)
        elif policy.response_mode in ("reflective", "supportive"):
            target = "phi3_ollama"  # currently same; future: larger model
            reason = f"reflective_mode: mode={policy.response_mode}"

        # Default
        else:
            target = self._default_backend
            reason = "default_routing"

        # Health check — fallback if unhealthy
        if not self._health.is_healthy(target):
            healthy = self._health.get_healthy_backends()
            if healthy:
                target = healthy[0]
                reason = f"fallback_unhealthy: original unhealthy, using {target}"
                decision = RoutingDecision(
                    selected_backend=target, reason=reason, fallback_used=True
                )
            else:
                # No healthy backends
                decision = RoutingDecision(
                    selected_backend="none", reason="all_backends_unhealthy",
                    fallback_used=True,
                )
                self._routing_history.append(decision)
                return None, decision
        else:
            decision = RoutingDecision(selected_backend=target, reason=reason)

        self._routing_history.append(decision)
        backend = self._backends.get(target)
        return backend, decision

    async def get_router_diagnostics(self) -> dict:
        """Introspection: routing decisions and backend status."""
        recent = list(self._routing_history)[-10:]
        return {
            "registered_backends": list(self._backends.keys()),
            "healthy_backends": self._health.get_healthy_backends(),
            "unhealthy_backends": self._health.get_unhealthy_backends(),
            "recent_decisions": [
                {"backend": d.selected_backend, "reason": d.reason, "fallback": d.fallback_used}
                for d in recent
            ],
            "total_routing_decisions": len(self._routing_history),
        }
