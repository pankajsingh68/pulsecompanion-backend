"""Adaptation limit constants and helpers."""

from orchestration.models import ResponseTone, VerbosityLevel
from safety.safety_models import AdaptationBounds

DEFAULT_BOUNDS = AdaptationBounds()

_VERBOSITY_ORDER = [
    VerbosityLevel.MINIMAL,
    VerbosityLevel.SHORT,
    VerbosityLevel.NORMAL,
    VerbosityLevel.DETAILED,
]

_TONE_ORDER = [
    ResponseTone.CALM,
    ResponseTone.WARM,
    ResponseTone.NEUTRAL,
    ResponseTone.TECHNICAL,
    ResponseTone.ENERGETIC,
]


def get_verbosity_index(v: VerbosityLevel) -> int:
    """Get ordinal index of a verbosity level."""
    try:
        return _VERBOSITY_ORDER.index(v)
    except ValueError:
        return 2  # NORMAL


def get_tone_index(t: ResponseTone) -> int:
    """Get ordinal index of a tone."""
    try:
        return _TONE_ORDER.index(t)
    except ValueError:
        return 2  # NEUTRAL
