"""
test_recovery.py — Unit tests for RecoveryManager.

Verifies:
  - Recovery phases advance in order.
  - Maximum recovery duration bound is enforced.
  - Timing and queue durations are tracked separately.
  - Recovery does not reset to phase zero.
"""
from __future__ import annotations

import pytest
from lifelane_engine.traffic.recovery import RecoveryManager, RecoveryPhase


class TestRecoveryManager:
    def test_initial_phase_is_serve_delayed(self):
        rm = RecoveryManager("J1")
        rm.start(now=0.0)
        assert rm.phase == RecoveryPhase.SERVE_DELAYED

    def test_advances_to_timing_recovery_after_max_delay(self):
        rm = RecoveryManager("J1")
        rm.start(now=0.0)
        # Tick past max_delay_service_s (default 60)
        for i in range(65):
            rm.tick(now=float(i + 1), queue_cleared=False)
        assert rm.phase in (RecoveryPhase.TIMING_RECOVERY, RecoveryPhase.QUEUE_RECOVERY,
                            RecoveryPhase.COMPLETE)

    def test_completes_when_queue_cleared(self):
        rm = RecoveryManager("J1")
        rm.start(now=0.0)
        # Advance through delay service
        for i in range(65):
            rm.tick(now=float(i + 1), queue_cleared=False)
        # Signal queue cleared
        for i in range(5):
            phase = rm.tick(now=float(66 + i), queue_cleared=True)
        assert rm.phase == RecoveryPhase.COMPLETE
        assert rm.is_complete()

    def test_max_recovery_duration_forces_complete(self):
        rm = RecoveryManager("J1")
        rm.start(now=0.0)
        # Tick past max_recovery_duration_s (default 120) without queue cleared
        for i in range(130):
            rm.tick(now=float(i + 1), queue_cleared=False)
        assert rm.phase == RecoveryPhase.COMPLETE

    def test_summary_includes_durations(self):
        rm = RecoveryManager("J1")
        rm.start(now=0.0)
        for i in range(130):
            rm.tick(now=float(i + 1), queue_cleared=(i > 70))
        s = rm.summary()
        assert "timing_recovery_duration_s" in s
        assert "queue_recovery_duration_s" in s
        assert "total_recovery_duration_s" in s
        assert s["junction_id"] == "J1"

    def test_tick_without_start_raises(self):
        rm = RecoveryManager("J1")
        with pytest.raises(RuntimeError):
            rm.tick(now=1.0)

    def test_does_not_reset_to_phase_zero(self):
        """After passage, recovery continues from where signal was, not phase zero.

        In Phase 1 this is validated by checking that recovery does NOT
        blindly restart phase indexing — the phase enum advances forward only.
        """
        rm = RecoveryManager("J1")
        rm.start(now=0.0)
        phases_seen = []
        for i in range(130):
            phase = rm.tick(now=float(i + 1), queue_cleared=(i > 70))
            phases_seen.append(phase)
        # Phases should only advance (never go backward in enum order)
        phase_values = [p.value for p in phases_seen]
        assert phase_values == sorted(phase_values) or all(
            a <= b for a, b in zip(phase_values, phase_values[1:])
        ), "Recovery phases must not go backward (no reset to phase zero)"

