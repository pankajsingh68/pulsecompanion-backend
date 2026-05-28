"""Emotional Intelligence Core — orchestrates all 5 modules into one cycle.

Pipeline: Fusion → Rhythm → Interaction → Regulation → Pattern Memory
"""

from __future__ import annotations

from dataclasses import dataclass

from emotion.emotional_fusion_engine import (
    EmotionalFusionEngine, EmotionalSignal, UnifiedEmotionalState,
)
from emotion.conversational_rhythm_engine import (
    ConversationalRhythmEngine, RhythmSignal, RhythmState,
)
from emotion.adaptive_interaction_engine import (
    AdaptiveInteractionEngine, InteractionDirective,
)
from emotion.overload_regulation_controller import (
    OverloadRegulationController, RegulationDecision,
)
from emotion.relational_pattern_memory import (
    RelationalPatternMemory, RelationalPatternState,
)
from utils.logger import get_logger

logger = get_logger(__name__)

CYCLE_VERSION = 1


@dataclass(frozen=True)
class CycleOutput:
    """Complete output of one emotional intelligence cycle."""
    emotional_state: UnifiedEmotionalState
    rhythm_state: RhythmState
    directive: InteractionDirective
    regulation: RegulationDecision
    pattern: RelationalPatternState
    cycle_monotonic: float
    cycle_version: int


class EmotionalIntelligenceCore:
    """Orchestrates all 5 emotional intelligence modules."""

    def __init__(self) -> None:
        self.fusion = EmotionalFusionEngine()
        self.rhythm = ConversationalRhythmEngine()
        self.interaction = AdaptiveInteractionEngine()
        self.regulation = OverloadRegulationController()
        self.pattern_memory = RelationalPatternMemory()
        self._cycle_count: int = 0

    async def run_cycle(
        self,
        signals: list[EmotionalSignal],
        rhythm_signal: RhythmSignal,
        degraded: bool = False,
    ) -> CycleOutput:
        """Run one complete emotional intelligence cycle.

        RelationalPatternMemory updates AFTER cycle output is assembled.
        If any module raises, degrade gracefully — partial output is valid.
        """
        self._cycle_count += 1

        # Module 1: Emotional Fusion
        emotional_state = self.fusion.process_cycle(signals, degraded=degraded)

        # Module 2: Conversational Rhythm
        rhythm_state = self.rhythm.process_cycle(rhythm_signal)

        # Module 3: Adaptive Interaction
        directive = self.interaction.process_cycle(emotional_state, rhythm_state)

        # Module 4: Overload Regulation
        regulation = self.regulation.process_cycle(emotional_state, rhythm_state)

        # Module 5: Relational Pattern Memory (post-cycle update)
        pattern = self.pattern_memory.update_after_cycle(
            stress=emotional_state.stress,
            engagement=emotional_state.engagement,
            openness=emotional_state.emotional_openness,
            overload_detected=regulation.overload_detected,
            recovery_state=emotional_state.recovery_state,
            overload_severity=regulation.overload_severity,
        )

        output = CycleOutput(
            emotional_state=emotional_state,
            rhythm_state=rhythm_state,
            directive=directive,
            regulation=regulation,
            pattern=pattern,
            cycle_monotonic=rhythm_signal.timestamp,
            cycle_version=CYCLE_VERSION,
        )

        return output
