"""Shared utility functions used across the PulseCompanion backend."""

from datetime import datetime, timezone
from typing import Any


def clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """Clamp a value between min and max bounds.

    Args:
        value: The value to clamp.
        min_val: Minimum allowed value (default 0.0).
        max_val: Maximum allowed value (default 1.0).

    Returns:
        The clamped value within [min_val, max_val].

    Example:
        >>> clamp(1.5)
        1.0
        >>> clamp(-0.3)
        0.0
        >>> clamp(0.7)
        0.7
    """
    return max(min_val, min(value, max_val))


def get_utc_timestamp() -> str:
    """Return the current UTC time as an ISO 8601 formatted string.

    Returns:
        ISO format UTC timestamp string.

    Example:
        >>> ts = get_utc_timestamp()
        >>> ts.endswith('+00:00')
        True
    """
    return datetime.now(timezone.utc).isoformat()


def safe_get(d: dict | None, key: str, default: Any = None) -> Any:
    """Safely get a value from a potentially None dictionary.

    Args:
        d: Dictionary to retrieve from, or None.
        key: Key to look up.
        default: Value to return if dict is None or key is missing.

    Returns:
        The value for key if dict is not None and key exists, otherwise default.

    Example:
        >>> safe_get({"a": 1}, "a")
        1
        >>> safe_get(None, "a", 0)
        0
        >>> safe_get({"a": 1}, "b", "missing")
        'missing'
    """
    if d is None:
        return default
    return d.get(key, default)
