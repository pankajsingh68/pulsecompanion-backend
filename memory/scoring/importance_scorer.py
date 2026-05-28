"""Memory importance scorer — decides what's worth remembering."""

from memory.schemas import (
    EpisodeType, ImportanceScore, MemoryImportance, MemoryTier,
)
from utils.helpers import clamp


class MemoryImportanceScorer:
    """Decides whether a memory is worth storing and in which tier."""

    WEIGHTS = {
        "stress_intensity": 0.30,
        "emotional_significance": 0.25,
        "novelty": 0.20,
        "engagement": 0.15,
        "recurrence": 0.10,
    }

    def score(
        self,
        message: str,
        human_state: dict,
        prior_state: dict | None = None,
        session_history: list[dict] | None = None,
    ) -> ImportanceScore:
        """Score a memory's importance. Returns full breakdown."""
        stress = human_state.get("stress", 0.0)
        fatigue = human_state.get("fatigue", 0.0)
        engagement = human_state.get("engagement", 0.5)
        ux_mode = human_state.get("ux_mode", "normal")

        stress_score = self._stress_factor(stress, fatigue)
        significance_score = self._significance_factor(human_state, prior_state)
        novelty_score = self._novelty_factor(ux_mode, session_history or [])
        engagement_score = self._engagement_factor(engagement, len(message.split()))
        recurrence_score = self._recurrence_factor(ux_mode, session_history or [])

        raw = (
            stress_score * self.WEIGHTS["stress_intensity"]
            + significance_score * self.WEIGHTS["emotional_significance"]
            + novelty_score * self.WEIGHTS["novelty"]
            + engagement_score * self.WEIGHTS["engagement"]
            + recurrence_score * self.WEIGHTS["recurrence"]
        )
        score_val = clamp(raw)

        if score_val >= 0.8:
            label = MemoryImportance.CRITICAL
        elif score_val >= 0.6:
            label = MemoryImportance.HIGH
        elif score_val >= 0.3:
            label = MemoryImportance.MEDIUM
        else:
            label = MemoryImportance.LOW

        episode_type = self._detect_episode(human_state, prior_state, score_val)
        tier = self._recommend_tier(score_val, episode_type)

        return ImportanceScore(
            score=round(score_val, 3),
            label=label,
            contributing_factors={
                "stress_intensity": round(stress_score, 3),
                "emotional_significance": round(significance_score, 3),
                "novelty": round(novelty_score, 3),
                "engagement": round(engagement_score, 3),
                "recurrence": round(recurrence_score, 3),
            },
            should_store=score_val >= 0.2,
            recommended_tier=tier,
            episode_type=episode_type,
        )

    def _stress_factor(self, stress: float, fatigue: float) -> float:
        return clamp(max(stress, fatigue * 0.8))

    def _significance_factor(self, state: dict, prior: dict | None) -> float:
        if prior is None:
            return 0.3
        stress_delta = abs(state.get("stress", 0) - prior.get("stress", 0))
        fatigue_delta = abs(state.get("fatigue", 0) - prior.get("fatigue", 0))
        mode_changed = state.get("ux_mode") != prior.get("ux_mode")
        return clamp(stress_delta * 1.5 + fatigue_delta * 1.0 + (0.3 if mode_changed else 0.0))

    def _novelty_factor(self, ux_mode: str, history: list[dict]) -> float:
        if not history:
            return 0.8
        seen_modes = [h.get("ux_mode") for h in history]
        if ux_mode not in seen_modes:
            return 0.7
        occurrences = seen_modes.count(ux_mode)
        return clamp(1.0 / (occurrences + 1))

    def _engagement_factor(self, engagement: float, word_count: int) -> float:
        length_factor = clamp(word_count / 60)
        return clamp(engagement * 0.6 + length_factor * 0.4)

    def _recurrence_factor(self, ux_mode: str, history: list[dict]) -> float:
        occurrences = sum(1 for h in history if h.get("ux_mode") == ux_mode)
        if occurrences >= 3:
            return 0.8
        if occurrences >= 2:
            return 0.5
        return 0.1

    def _detect_episode(
        self, state: dict, prior: dict | None, importance: float
    ) -> EpisodeType | None:
        stress = state.get("stress", 0)
        fatigue = state.get("fatigue", 0)
        focus = state.get("focus", 0)
        recovery_need = state.get("recovery_need", 0)

        if stress >= 0.8 and fatigue >= 0.7:
            return EpisodeType.BURNOUT_SIGNAL
        if state.get("ux_mode") == "overload_protection":
            return EpisodeType.OVERLOAD_EVENT
        if focus >= 0.75 and stress <= 0.25:
            return EpisodeType.FLOW_STATE
        if recovery_need >= 0.7:
            return EpisodeType.FATIGUE_ACCUMULATION
        if prior and abs(stress - prior.get("stress", 0)) > 0.25:
            return EpisodeType.EMOTIONAL_SHIFT
        if prior and stress < prior.get("stress", 0) - 0.2:
            return EpisodeType.RECOVERY_EVENT
        if stress >= 0.7 and (prior is None or prior.get("stress", 0) < 0.4):
            return EpisodeType.STRESS_SPIKE
        return None

    def _recommend_tier(
        self, score: float, episode_type: EpisodeType | None
    ) -> MemoryTier:
        if episode_type in [
            EpisodeType.BURNOUT_SIGNAL, EpisodeType.OVERLOAD_EVENT,
            EpisodeType.FLOW_STATE, EpisodeType.EMOTIONAL_SHIFT,
            EpisodeType.RECOVERY_EVENT,
        ]:
            return MemoryTier.EPISODIC
        if score >= 0.6:
            return MemoryTier.EPISODIC
        if score >= 0.3:
            return MemoryTier.SEMANTIC
        return MemoryTier.WORKING
