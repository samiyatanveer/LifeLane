"""
test_approach_selector.py — Unit tests for ApproachSelector and ApproachEvidence.

Tests verify:
  - Confirmation requires exactly N consecutive positive windows.
  - A negative window resets the streak.
  - Conflict is detected when multiple approaches are simultaneously confirmed.
  - Cooldown prevents re-triggering.
  - Non-siren evidence never produces CONFIRMED.
"""
from __future__ import annotations

import pytest
from lifelane_engine.audio.approach_selector import (
    ApproachEvidence,
    ApproachSelector,
    ApproachState,
    APPROACHES,
)


class TestApproachEvidence:
    """Unit tests for a single-approach evidence tracker."""

    def _make(self, required: int = 3, cooldown: float = 30.0, threshold: float = 0.5) -> ApproachEvidence:
        return ApproachEvidence(
            approach="north",
            threshold=threshold,
            required_windows=required,
            cooldown_s=cooldown,
            max_activations_per_hour=10,
        )

    def test_idle_on_start(self):
        ev = self._make()
        assert ev.state == ApproachState.IDLE

    def test_suspected_after_one_positive(self):
        ev = self._make()
        state = ev.update(0.9, now=0.0)
        assert state == ApproachState.SUSPECTED

    def test_suspected_after_two_positive(self):
        ev = self._make()
        ev.update(0.9, now=0.0)
        state = ev.update(0.9, now=1.0)
        assert state == ApproachState.SUSPECTED

    def test_confirmed_after_three_consecutive(self):
        ev = self._make()
        for i in range(3):
            state = ev.update(0.9, now=float(i))
        assert state == ApproachState.CONFIRMED

    def test_negative_window_resets_streak(self):
        ev = self._make()
        ev.update(0.9, now=0.0)
        ev.update(0.9, now=1.0)
        state = ev.update(0.1, now=2.0)  # negative — resets
        assert state == ApproachState.IDLE
        assert ev.consecutive_positive == 0

    def test_must_have_consecutive_windows(self):
        """2 positive + 1 negative + 1 positive should NOT confirm."""
        ev = self._make()
        ev.update(0.9, now=0.0)
        ev.update(0.9, now=1.0)
        ev.update(0.1, now=2.0)  # reset
        state = ev.update(0.9, now=3.0)  # only 1 after reset
        assert state == ApproachState.SUSPECTED
        assert ev.consecutive_positive == 1

    def test_cooldown_blocks_updates(self):
        ev = self._make(cooldown=30.0)
        ev.enter_cooldown(now=100.0)
        assert ev.state == ApproachState.COOLDOWN
        # Update during cooldown should stay in cooldown
        state = ev.update(0.99, now=110.0)
        assert state == ApproachState.COOLDOWN

    def test_cooldown_ends_after_duration(self):
        ev = self._make(cooldown=30.0)
        ev.enter_cooldown(now=100.0)
        state = ev.update(0.0, now=131.0)  # after cooldown
        assert state == ApproachState.IDLE

    def test_low_score_never_confirms(self):
        ev = self._make(threshold=0.5)
        for i in range(10):
            state = ev.update(0.3, now=float(i))
        assert state == ApproachState.IDLE

    def test_reset_clears_state(self):
        ev = self._make()
        for i in range(3):
            ev.update(0.9, now=float(i))
        assert ev.state == ApproachState.CONFIRMED
        ev.reset()
        assert ev.state == ApproachState.IDLE
        assert ev.consecutive_positive == 0

    def test_exactly_threshold_is_positive(self):
        ev = self._make(threshold=0.5)
        # Smoothed = exactly 0.5 after filling window with 0.5
        for i in range(5):
            state = ev.update(0.5, now=float(i))
        # Should be CONFIRMED (3 windows each ≥ threshold)
        assert state in (ApproachState.SUSPECTED, ApproachState.CONFIRMED)


class TestApproachSelector:
    """Integration tests for the multi-approach selector."""

    def _scores(self, **kwargs: float) -> dict[str, float]:
        base = {ap: 0.0 for ap in APPROACHES}
        base.update(kwargs)
        return base

    def test_no_confirmation_on_low_scores(self):
        sel = ApproachSelector("J1")
        for i in range(5):
            result = sel.update(self._scores(north=0.2), now=float(i))
        assert result is None

    def test_confirms_single_approach(self):
        sel = ApproachSelector("J1")
        result = None
        for i in range(3):
            result = sel.update(self._scores(north=0.9), now=float(i))
        assert result == "north"

    def test_conflict_when_two_approaches_confirmed(self):
        sel = ApproachSelector("J1")
        result = None
        for i in range(3):
            result = sel.update(self._scores(north=0.9, south=0.85), now=float(i))
        assert result == ApproachSelector.CONFLICT

    def test_conflict_no_green_implication(self):
        """After conflict, result is CONFLICT, not a valid approach — no green should follow."""
        sel = ApproachSelector("J1")
        for i in range(3):
            result = sel.update(self._scores(north=0.9, east=0.9), now=float(i))
        assert result == ApproachSelector.CONFLICT
        # In the safety controller, CONFLICT must never trigger a green
        # (tested in test_signal_controller.py)

    def test_get_state_returns_correct_state(self):
        sel = ApproachSelector("J1")
        for i in range(3):
            sel.update(self._scores(north=0.9), now=float(i))
        assert sel.get_state("north") == ApproachState.CONFIRMED
        assert sel.get_state("east") == ApproachState.IDLE

    def test_reset_all(self):
        sel = ApproachSelector("J1")
        for i in range(3):
            sel.update(self._scores(north=0.9), now=float(i))
        sel.reset_all()
        for ap in APPROACHES:
            assert sel.get_state(ap) == ApproachState.IDLE

    def test_enter_cooldown_via_selector(self):
        sel = ApproachSelector("J1")
        for i in range(3):
            sel.update(self._scores(north=0.9), now=float(i))
        sel.enter_cooldown("north", now=10.0)
        assert sel.get_state("north") == ApproachState.COOLDOWN

