"""Mode hysteresis — requires sustained triggers before committing mode changes."""


class ModeHysteresis:
    """Mode must be sustained N consecutive turns before committing.

    Prevents: single-spike stress reading triggering overload_protection.

    Config:
      overload_protection: requires 2 consecutive triggers
      calm_minimal: requires 2 consecutive triggers
      focus_mode: requires 1 (fast to enter focus)
      normal: requires 1 (fast to return to normal)
    """

    REQUIRED_CONSECUTIVE: dict[str, int] = {
        "overload_protection": 2,
        "calm_minimal": 2,
        "focus_mode": 1,
        "normal": 1,
    }

    def __init__(self) -> None:
        self._pending: dict[str, tuple[str, int]] = {}  # session → (mode, count)
        self._committed: dict[str, str] = {}  # session → committed mode

    def confirm_mode(self, session_id: str, proposed_mode: str) -> str:
        """Return committed mode (may differ from proposed if not yet sustained).

        Args:
            session_id: The session.
            proposed_mode: The mode the rules want to transition to.

        Returns:
            The mode that should actually be used.
        """
        required = self.REQUIRED_CONSECUTIVE.get(proposed_mode, 1)
        current_committed = self._committed.get(session_id, "normal")

        if proposed_mode == current_committed:
            # Already in this mode — no change needed
            self._pending.pop(session_id, None)
            return proposed_mode

        # Check pending
        pending = self._pending.get(session_id)
        if pending and pending[0] == proposed_mode:
            # Same proposed mode as last time — increment count
            count = pending[1] + 1
            if count >= required:
                # Sustained long enough — commit
                self._committed[session_id] = proposed_mode
                self._pending.pop(session_id, None)
                return proposed_mode
            else:
                # Not yet sustained — hold current
                self._pending[session_id] = (proposed_mode, count)
                return current_committed
        else:
            # New proposed mode — start counting
            if required <= 1:
                # Immediate commit
                self._committed[session_id] = proposed_mode
                self._pending.pop(session_id, None)
                return proposed_mode
            else:
                self._pending[session_id] = (proposed_mode, 1)
                return current_committed
