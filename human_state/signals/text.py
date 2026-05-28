"""Text signal extraction — keyword-based scoring from message content."""

from utils.helpers import clamp


class TextSignalExtractor:
    """Extracts normalized signal scores from text content only.

    No state inference here — just signal extraction.
    """

    STRESS_KEYWORDS: list[str] = [
        "urgent", "deadline", "overwhelmed", "anxious", "stressed",
        "panic", "help", "emergency", "stuck", "failing", "behind",
        "overdue", "pressure", "can't handle", "too much", "falling apart",
        "nightmare", "disaster", "impossible", "breaking",
    ]

    FOCUS_KEYWORDS: list[str] = [
        "working on", "building", "coding", "implementing", "designing",
        "creating", "need to", "trying to", "focus", "developing",
        "debugging", "writing", "researching", "analyzing", "figuring out",
        "deep work", "concentrated", "in the zone",
    ]

    FATIGUE_KEYWORDS: list[str] = [
        "tired", "exhausted", "can't think", "slow", "brain fog",
        "sleepy", "drained", "worn out", "no energy", "burned out",
        "running on empty", "barely functioning", "half asleep",
    ]

    ENGAGEMENT_KEYWORDS: list[str] = [
        "interesting", "excited", "love this", "fascinating", "curious",
        "want to learn", "tell me more", "how does", "why does",
        "what if", "great idea", "amazing", "brilliant",
    ]

    LOW_ENGAGEMENT_KEYWORDS: list[str] = [
        "boring", "whatever", "don't care", "meh", "fine", "ok",
        "sure", "whatever you say", "just do it",
    ]

    def extract(self, message: str) -> dict:
        """Extract normalized scores from message text.

        Returns:
            Dict with keys: stress, focus, fatigue, engagement,
            word_count, message_length.
            All score values: 0.0 - 1.0.
        """
        message_lower = message.lower()

        def score(keywords: list[str], multiplier: float, default: float | None = None) -> float | None:
            count = sum(1 for kw in keywords if kw in message_lower)
            if count == 0:
                return default
            return min(count * multiplier, 1.0)

        return {
            "stress": score(self.STRESS_KEYWORDS, 0.15, default=0.0),
            "focus": score(self.FOCUS_KEYWORDS, 0.2, default=0.5),
            "fatigue": score(self.FATIGUE_KEYWORDS, 0.25, default=0.2),
            "engagement": self._engagement_score(message_lower),
            "word_count": len(message.split()),
            "message_length": len(message),
        }

    def _engagement_score(self, message_lower: str) -> float:
        """Compute engagement from high/low engagement keyword balance."""
        high = sum(1 for kw in self.ENGAGEMENT_KEYWORDS if kw in message_lower)
        low = sum(1 for kw in self.LOW_ENGAGEMENT_KEYWORDS if kw in message_lower)
        base = 0.5
        return clamp(base + (high * 0.15) - (low * 0.15))
