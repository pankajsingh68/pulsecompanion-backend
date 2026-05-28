"""Episode detector — monitors state for sustained emotional patterns."""

from memory.schemas import EpisodeType, ImportanceScore
from utils.logger import get_logger

logger = get_logger(__name__)


class EpisodeDetector:
    """Detects sustained emotional episodes (not single spikes)."""

    SUSTAINED_THRESHOLD = 3

    def __init__(self) -> None:
        self._stress_streak: int = 0
        self._focus_streak: int = 0
        self._fatigue_streak: int = 0
        self._last_episode: EpisodeType | None = None

    def update(
        self, human_state: dict, scored: ImportanceScore
    ) -> EpisodeType | None:
        """Call on every message. Returns confirmed episode type
        only when pattern is sustained."""
        stress = human_state.get("stress", 0)
        focus = human_state.get("focus", 0)
        fatigue = human_state.get("fatigue", 0)

        # Track streaks
        if stress >= 0.65:
            self._stress_streak += 1
        else:
            self._stress_streak = max(0, self._stress_streak - 1)

        if focus >= 0.7 and stress <= 0.3:
            self._focus_streak += 1
        else:
            self._focus_streak = max(0, self._focus_streak - 1)

        if fatigue >= 0.65:
            self._fatigue_streak += 1
        else:
            self._fatigue_streak = max(0, self._fatigue_streak - 1)

        # Confirm episodes only when sustained
        confirmed = None

        if (self._stress_streak >= self.SUSTAINED_THRESHOLD
                and self._last_episode != EpisodeType.BURNOUT_SIGNAL):
            if fatigue >= 0.6:
                confirmed = EpisodeType.BURNOUT_SIGNAL
            else:
                confirmed = EpisodeType.STRESS_SPIKE

        elif (self._focus_streak >= self.SUSTAINED_THRESHOLD
              and self._last_episode != EpisodeType.FLOW_STATE):
            confirmed = EpisodeType.FLOW_STATE

        elif (self._fatigue_streak >= self.SUSTAINED_THRESHOLD
              and self._last_episode != EpisodeType.FATIGUE_ACCUMULATION):
            confirmed = EpisodeType.FATIGUE_ACCUMULATION

        # Detect recovery
        if (self._last_episode in [EpisodeType.STRESS_SPIKE, EpisodeType.BURNOUT_SIGNAL]
                and stress < 0.35):
            confirmed = EpisodeType.RECOVERY_EVENT

        if confirmed:
            self._last_episode = confirmed
            logger.info(
                "episode_confirmed",
                episode=confirmed.value,
                stress=stress, focus=focus, fatigue=fatigue,
            )

        return confirmed
