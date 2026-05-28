"""UX Orchestrator — main entry point for adaptive UX strategy computation."""

from __future__ import annotations

from datetime import datetime, timezone

from orchestration.models import UXStrategy
from orchestration.rules import (
    TOKEN_MAP,
    apply_cognitive_support_rules,
    apply_emotional_support_rules,
    apply_notification_rules,
    apply_pacing_rules,
    apply_tone_rules,
    apply_verbosity_rule,
)
from orchestration.temporal_adaptation import TemporalAdaptation
from orchestration.explainability import OrchestrationExplainer
from utils.logger import get_logger

logger = get_logger(__name__)


class UXOrchestrator:
    """Consumes RichHumanState → outputs UXStrategy.

    Replaces the bare determine_ux_mode() string for rich consumers.
    The old determine_ux_mode() still works for backward compat.
    """

    def __init__(self) -> None:
        self.temporal = TemporalAdaptation()
        self.explainer = OrchestrationExplainer()
        self._session_strategies: dict[str, UXStrategy] = {}

    async def orchestrate(
        self, session_id: str, human_state: dict
    ) -> UXStrategy:
        """Main async entry point.

        1. Read ux_mode from human_state (already computed by Phase 2)
        2. Apply all rule modules
        3. Apply temporal adaptation
        4. Build explainability
        5. Store + return UXStrategy

        Args:
            session_id: The session identifier.
            human_state: RichHumanState as dict.

        Returns:
            Fully computed UXStrategy.
        """
        prior = self._session_strategies.get(session_id)
        ux_mode = human_state.get("ux_mode", "normal")

        # Apply all rules
        verbosity = apply_verbosity_rule(ux_mode)
        tone, tone_reason = apply_tone_rules(human_state)
        suppress, delay, notif_reason = apply_notification_rules(human_state)
        cog_reduction, suggest_break, cog_reason = apply_cognitive_support_rules(
            human_state
        )
        pacing, anim_speed, ui_density = apply_pacing_rules(human_state)
        support_level, recovery_sup, support_reason = (
            apply_emotional_support_rules(human_state)
        )

        rule_outputs = {
            "tone_reason": tone_reason,
            "notif_reason": notif_reason,
            "cog_reason": cog_reason,
            "support_reason": support_reason,
        }

        # Build raw strategy
        strategy = UXStrategy(
            ux_mode=ux_mode,
            verbosity_level=verbosity,
            response_tone=tone,
            max_response_tokens=TOKEN_MAP.get(ux_mode, 512),
            suppress_notifications=suppress,
            interruption_sensitivity=1.0 - human_state.get("stress", 0),
            notification_delay_seconds=delay,
            cognitive_load_reduction=cog_reduction,
            suggest_break=suggest_break,
            proactive_assistance=human_state.get("engagement", 0.5) > 0.6,
            response_pacing=pacing,
            animation_speed=anim_speed,
            ui_density=ui_density,
            emotional_support_level=support_level,
            recovery_support=recovery_sup,
            reasoning=[],
            contributing_factors=self.explainer.build_contributing_factors(
                human_state
            ),
            confidence=human_state.get("inference_confidence", 0.5),
            timestamp=datetime.now(timezone.utc),
            session_id=session_id,
            prior_mode=prior.ux_mode if prior else None,
        )

        # Apply temporal moderation
        strategy = self.temporal.apply(strategy, prior)

        # Build reasoning
        strategy.reasoning = self.explainer.build_reasoning(
            human_state, strategy, rule_outputs
        )

        # Persist and return
        self._session_strategies[session_id] = strategy

        logger.info(
            "ux_strategy_computed",
            session_id=session_id,
            ux_mode=strategy.ux_mode,
            verbosity=strategy.verbosity_level.value,
            tone=strategy.response_tone.value,
            suggest_break=strategy.suggest_break,
            suppress_notifs=strategy.suppress_notifications,
            confidence=round(strategy.confidence, 3),
        )

        return strategy

    def get_current_strategy(self, session_id: str) -> UXStrategy | None:
        """Get the last computed strategy for a session."""
        return self._session_strategies.get(session_id)
