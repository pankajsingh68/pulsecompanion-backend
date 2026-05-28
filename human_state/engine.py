"""Human State Engine — main entry point for Phase 2 state estimation.

Replaces HeuristicStateEstimator as the system's brain.
Preserves backward-compatible interface.

Flow:
    RawSignals
    → TextSignalExtractor
    → BiometricSignalProcessor
    → BehaviorSignalExtractor
    → SignalScores (fusion input)
    → MultimodalFusion
    → RichHumanState (raw)
    → TemporalStateTracker (smoothed)
    → SessionStateStore (persisted)
    → return smoothed RichHumanState
"""

from __future__ import annotations

from datetime import datetime, timezone

from human_state.models import RawSignals, RichHumanState, SignalScores
from human_state.signals.text import TextSignalExtractor
from human_state.signals.biometrics import BiometricSignalProcessor
from human_state.signals.behavior import BehaviorSignalExtractor
from human_state.fusion.multimodal import MultimodalFusion
from human_state.session.state_store import SessionStateStore
from utils.logger import get_logger

logger = get_logger(__name__)


class HumanStateEngine:
    """Main entry point for Phase 2 Human State Engine.

    Replaces HeuristicStateEstimator as the system's brain.
    Preserves backward-compatible interface via estimate_state().
    """

    def __init__(self) -> None:
        self.text_extractor = TextSignalExtractor()
        self.bio_processor = BiometricSignalProcessor()
        self.behavior_extractor = BehaviorSignalExtractor()
        self.fusion = MultimodalFusion()
        self.session_store = SessionStateStore()

    async def process(
        self,
        session_id: str,
        message: str,
        biometric_hint: dict | None = None,
        behavioral_context: dict | None = None,
    ) -> RichHumanState:
        """Main async entry point.

        Args:
            session_id: The session identifier.
            message: User's text message.
            biometric_hint: Optional dict with hr, hrv, gsr.
            behavioral_context: Optional dict with message_count, time_since_last_s.

        Returns:
            Smoothed RichHumanState for this session.
        """
        start_time = datetime.now(timezone.utc)

        # Build raw signals container
        raw = RawSignals(
            message=message,
            message_length=len(message),
            message_word_count=len(message.split()),
            hr=biometric_hint.get("hr") if biometric_hint else None,
            hrv=biometric_hint.get("hrv") if biometric_hint else None,
            gsr=biometric_hint.get("gsr") if biometric_hint else None,
            session_message_count=(
                behavioral_context.get("message_count", 0)
                if behavioral_context
                else 0
            ),
            time_since_last_message_s=(
                behavioral_context.get("time_since_last_s")
                if behavioral_context
                else None
            ),
            session_id=session_id,
        )

        # Extract signals from each modality
        text_scores = self.text_extractor.extract(message)
        bio_scores = self.bio_processor.process(raw.hr, raw.hrv, raw.gsr)
        behavior_scores = self.behavior_extractor.extract(raw)

        # Build contributing sources list
        sources = ["text"]
        if bio_scores:
            sources.append("biometrics")
        if behavior_scores:
            sources.append("behavior")

        # Assemble SignalScores
        signals = SignalScores(
            text_stress=text_scores.get("stress"),
            text_focus=text_scores.get("focus"),
            text_fatigue=text_scores.get("fatigue"),
            text_engagement=text_scores.get("engagement"),
            bio_stress=bio_scores.get("bio_stress"),
            bio_fatigue=bio_scores.get("bio_fatigue"),
            bio_stability=bio_scores.get("bio_stability"),
            behavior_cognitive_load=behavior_scores.get("cognitive_load"),
            behavior_engagement=behavior_scores.get("engagement_from_length"),
            contributing_sources=sources,
        )

        # Get prior state for temporal context
        prior = self.session_store.get_current_state(session_id)

        # Fuse all signals into raw state
        raw_state = self.fusion.fuse(signals, prior_state=prior)

        # Smooth via temporal tracker
        smoothed_state = self.session_store.update_state(session_id, raw_state)

        elapsed_ms = (
            datetime.now(timezone.utc) - start_time
        ).total_seconds() * 1000
        logger.info(
            "human_state_computed",
            session_id=session_id,
            ux_mode=smoothed_state.ux_mode,
            stress=round(smoothed_state.stress, 3),
            fatigue=round(smoothed_state.fatigue, 3),
            cognitive_load=round(smoothed_state.cognitive_load, 3),
            trend=smoothed_state.trend,
            sources=sources,
            latency_ms=round(elapsed_ms, 2),
        )

        return smoothed_state

    def estimate_state(
        self, message: str, biometric_hint: dict | None = None
    ):
        """BACKWARD COMPATIBLE METHOD.

        Called by graph/nodes/state_estimator.py as:
            estimator.estimate_state(message, biometric_hint)

        Runs synchronous fallback using legacy heuristic logic when
        called from a sync context. Returns legacy HumanState.

        Use engine.process() for the full async pipeline.
        """
        import asyncio

        from models.human_state import HumanState

        # Try to run async process in sync context
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is None:
            # No running loop — safe to use asyncio.run
            rich_state = asyncio.run(
                self.process("legacy_sync", message, biometric_hint)
            )
            return HumanState(**rich_state.to_legacy_human_state())

        # Already in async context — fall back to legacy estimator
        # to avoid nested event loop issues
        from emotion.estimator import HeuristicStateEstimator

        return HeuristicStateEstimator()._estimate_legacy(message, biometric_hint)
