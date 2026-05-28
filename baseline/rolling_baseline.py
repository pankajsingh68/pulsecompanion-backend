"""Rolling baseline computation using exponential moving average."""


class RollingBaseline:
    """Computes personalized baseline for a single metric (HR or HRV).

    Uses exponential moving average over session history.
    Prevents: using population averages that don't fit the user.
    """

    def __init__(self, metric: str, alpha: float = 0.1) -> None:
        self.metric = metric
        self.alpha = alpha
        self._baseline: float | None = None
        self._sample_count: int = 0

    def update(self, value: float) -> float:
        """Update baseline with new observation. Returns current baseline."""
        if self._baseline is None:
            self._baseline = value
        else:
            self._baseline = self.alpha * value + (1 - self.alpha) * self._baseline
        self._sample_count += 1
        return self._baseline

    def is_calibrated(self) -> bool:
        """Need at least 10 samples before baseline is reliable."""
        return self._sample_count >= 10

    def deviation(self, value: float) -> float:
        """How far is this value from baseline? Normalized."""
        if self._baseline is None:
            return 0.0
        return (value - self._baseline) / max(self._baseline, 1.0)

    @property
    def current(self) -> float | None:
        """Current baseline value."""
        return self._baseline
