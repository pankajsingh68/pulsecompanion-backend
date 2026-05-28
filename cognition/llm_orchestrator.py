"""LLM Orchestrator — safe, bounded, fallback-aware LLM call handler.

The ONLY place in the codebase that calls an LLM.
Everything else is runtime logic.
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from cognition.prompt_conditioner import ConditionedPrompt, PromptConditioner
from cognition.response_constraint_enforcer import (
    EnforcedResponse, FALLBACKS, ResponseConstraintEnforcer,
)
from cognition.response_policy_engine import ResponsePolicy, ResponsePolicyEngine
from emotion.emotional_intelligence_core import CycleOutput
from utils.logger import get_logger

logger = get_logger(__name__)

ORCHESTRATION_VERSION = 1
LLM_TIMEOUT_S = 3.0


class LLMBackend(Protocol):
    async def complete(self, system_prompt: str, user_context: str, max_sentences: int) -> str: ...


class StubLLMBackend:
    """Returns mode-appropriate fallback text."""

    async def complete(self, system_prompt: str, user_context: str, max_sentences: int) -> str:
        for mode, fallback in FALLBACKS.items():
            if mode in system_prompt.lower():
                return fallback
        return FALLBACKS["neutral"]


@dataclass(frozen=True)
class OrchestrationResult:
    raw_response: str
    enforced_response: EnforcedResponse
    policy_applied: ResponsePolicy
    prompt_used: ConditionedPrompt
    latency_ms: float
    used_fallback: bool
    fallback_reason: str | None
    lineage_id: UUID
    session_id: str
    monotonic_timestamp: float
    orchestration_version: int


class LLMOrchestrator:
    """Orchestrates the full response generation pipeline.

    Flow: Policy → Router → Backend → Enforce → Result
    Owns router + health monitor. Backend selection is state-aware.
    """

    def __init__(self, bus=None, llm_backend: LLMBackend | None = None, router=None) -> None:
        self._bus = bus
        self._policy_engine = ResponsePolicyEngine()
        self._conditioner = PromptConditioner()
        self._enforcer = ResponseConstraintEnforcer(bus=bus)
        self._history: deque[OrchestrationResult] = deque(maxlen=100)
        self._fallback_log: deque[dict] = deque(maxlen=50)
        self._silence_count: int = 0
        self._fallback_count: int = 0
        self._timeout_count: int = 0
        self._total_latency: float = 0.0
        self._call_count: int = 0

        # Router integration
        from cognition.llm_router import LLMRouter
        from cognition.llm_health_monitor import LLMHealthMonitor

        self._health_monitor = LLMHealthMonitor()
        self._router = router

        if self._router is None:
            # Build default router with provided or stub backend
            default_backend = llm_backend or StubLLMBackend()
            self._router = LLMRouter(
                backends={"phi3_ollama": default_backend},
                health_monitor=self._health_monitor,
            )
        self._fallback_backend = StubLLMBackend()

    async def orchestrate(
        self,
        cycle_output: CycleOutput,
        lineage_id: UUID,
        session_id: str,
        timestamp: float,
        silence_duration: float = 0.0,
        user_spoke: bool = True,
    ) -> OrchestrationResult | None:
        """Full orchestration flow. Returns None when silence is chosen."""
        start = time.monotonic()

        # 1. Evaluate policy
        policy = self._policy_engine.evaluate(
            cycle_output, silence_duration=silence_duration,
            user_spoke_this_turn=user_spoke, timestamp=timestamp,
        )
        await self._emit("cognition.policy_evaluated", {
            "mode": policy.response_mode, "lineage_id": str(lineage_id),
        })

        # 2. Silence decision
        if not policy.should_respond:
            self._silence_count += 1
            await self._emit("cognition.silence", {
                "reason": policy.silence_reason, "lineage_id": str(lineage_id),
                "session_id": session_id,
            })
            return None

        # 3. Build prompt
        prompt = self._conditioner.build(policy, cycle_output)
        await self._emit("cognition.prompt_built", {
            "mode": prompt.response_mode, "lineage_id": str(lineage_id),
        })

        # 4. Call LLM via router (with timeout + fallback)
        raw_response = ""
        used_fallback = False
        fallback_reason = None

        # Select backend via router
        emotional_dict = {
            "cognitive_load": cycle_output.emotional_state.cognitive_load,
            "overload_detected": cycle_output.regulation.overload_detected,
        }
        backend, routing_decision = self._router.select_backend(policy, emotional_dict)

        if backend is None:
            used_fallback = True
            fallback_reason = "no_healthy_backend"
            raw_response = FALLBACKS.get(policy.response_mode, FALLBACKS["neutral"])
        else:
            try:
                llm_start = time.monotonic()
                raw_response = await asyncio.wait_for(
                    backend.complete(
                        prompt.system_prompt + "\n" + prompt.behavioral_constraints,
                        "", prompt.max_sentences,
                    ),
                    timeout=LLM_TIMEOUT_S,
                )
                llm_latency = (time.monotonic() - llm_start) * 1000
                self._health_monitor.record_success(
                    routing_decision.selected_backend, llm_latency
                )
            except asyncio.TimeoutError:
                used_fallback = True
                fallback_reason = "timeout"
                self._timeout_count += 1
                self._health_monitor.record_failure(routing_decision.selected_backend)
                raw_response = FALLBACKS.get(policy.response_mode, FALLBACKS["neutral"])
            except Exception as e:
                # One retry
                try:
                    raw_response = await asyncio.wait_for(
                        backend.complete(
                            prompt.system_prompt + "\n" + prompt.behavioral_constraints,
                            "", prompt.max_sentences,
                        ),
                        timeout=LLM_TIMEOUT_S,
                    )
                    llm_latency = (time.monotonic() - llm_start) * 1000
                    self._health_monitor.record_success(
                        routing_decision.selected_backend, llm_latency
                    )
                except Exception:
                    used_fallback = True
                    fallback_reason = f"llm_error: {e}"
                    self._health_monitor.record_failure(routing_decision.selected_backend)
                    raw_response = FALLBACKS.get(policy.response_mode, FALLBACKS["neutral"])

        if used_fallback:
            self._fallback_count += 1
            self._fallback_log.append({"reason": fallback_reason, "mode": policy.response_mode})
            await self._emit("cognition.fallback_used", {
                "reason": fallback_reason, "lineage_id": str(lineage_id),
            })

        # 5. Enforce constraints
        enforced = self._enforcer.enforce(raw_response, policy)

        # 6. Emit completion
        latency_ms = (time.monotonic() - start) * 1000
        self._total_latency += latency_ms
        self._call_count += 1

        await self._emit("cognition.response_generated", {
            "mode": policy.response_mode, "lineage_id": str(lineage_id),
            "used_fallback": used_fallback, "latency_ms": round(latency_ms, 2),
        })

        result = OrchestrationResult(
            raw_response=raw_response,
            enforced_response=enforced,
            policy_applied=policy,
            prompt_used=prompt,
            latency_ms=round(latency_ms, 3),
            used_fallback=used_fallback,
            fallback_reason=fallback_reason,
            lineage_id=lineage_id,
            session_id=session_id,
            monotonic_timestamp=timestamp,
            orchestration_version=ORCHESTRATION_VERSION,
        )
        self._history.append(result)
        return result

    async def _emit(self, event_type: str, payload: dict) -> None:
        if self._bus:
            try:
                await self._bus.emit(event_type, payload)
            except Exception:
                pass

    async def get_orchestration_diagnostics(self) -> dict:
        avg_latency = self._total_latency / max(self._call_count, 1)
        return {
            "fallback_rate": self._fallback_count / max(self._call_count, 1),
            "silence_rate": self._silence_count / max(self._call_count + self._silence_count, 1),
            "avg_latency_ms": round(avg_latency, 2),
            "timeout_count": self._timeout_count,
            "total_calls": self._call_count,
            "mode_distribution": self._mode_distribution(),
        }

    def _mode_distribution(self) -> dict:
        modes: dict[str, int] = {}
        for r in self._history:
            m = r.policy_applied.response_mode
            modes[m] = modes.get(m, 0) + 1
        return modes
