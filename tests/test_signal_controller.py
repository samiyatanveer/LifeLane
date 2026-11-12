"""
test_signal_controller.py — Unit tests for JunctionSignalController.

Critical safety invariants tested:
  - Illegal state transitions raise SafetyViolation.
  - Siren alone NEVER grants a green signal.
  - Approach mismatch is rejected.
  - Expired requests are rejected.
  - Passage must be confirmed by vehicle ID, not by audio silence.
  - expire_and_reset always returns controller to NORMAL.
"""
from __future__ import annotations

import time
import pytest
from lifelane_engine.traffic.signal_controller import (
    JunctionSignalController,
    ControllerState,
    SafetyViolation,
)
from lifelane_engine.ambulance.request import make_mock_request


def _make_controller(junction: str = "J1") -> JunctionSignalController:
    return JunctionSignalController(junction)


def _advance_to_confirmed(controller: JunctionSignalController) -> None:
    """Bring controller to CONFIRMED state via proper transitions."""
    controller.notify_siren_suspected("north")
    controller.notify_siren_confirmed("north")


class TestControllerStateTransitions:
    def test_initial_state_is_normal(self):
        c = _make_controller()
        assert c.state == ControllerState.NORMAL

    def test_normal_to_suspected(self):
        c = _make_controller()
        c.notify_siren_suspected("north")
        assert c.state == ControllerState.SUSPECTED

    def test_suspected_to_confirmed(self):
        c = _make_controller()
        c.notify_siren_suspected("north")
        c.notify_siren_confirmed("north")
        assert c.state == ControllerState.CONFIRMED

    def test_illegal_transition_raises(self):
        """Jumping NORMAL → CONFIRMED skipping SUSPECTED should raise."""
        c = _make_controller()
        with pytest.raises(SafetyViolation):
            # Directly try to transition from NORMAL to CONFIRMED (illegal)
            c._transition(ControllerState.CONFIRMED, "illegal jump")

    def test_illegal_jump_to_serving_raises(self):
        c = _make_controller()
        with pytest.raises(SafetyViolation):
            c._transition(ControllerState.SERVING, "illegal")

    def test_full_happy_path_states(self):
        c = _make_controller()
        now = 1000.0
        req = make_mock_request(approach="north", junction_id="J1", created_at=now, expiry_s=300.0)
        req.authorize(now=now)

        _advance_to_confirmed(c)
        assert c.state == ControllerState.CONFIRMED

        granted = c.request_priority(
            request_id=req.request_id,
            ambulance_id=req.ambulance_id,
            approach="north",
            expiry_at=req.expiry_at,
            confirmed_approach="north",
            now=now,
        )
        assert granted
        assert c.state == ControllerState.PREPARING

        c.execute_safe_transition_to_green(now=now)
        assert c.state == ControllerState.SERVING

        c.confirm_passage(req.ambulance_id, now=now + 15)
        assert c.state == ControllerState.EXITING

        c.begin_recovery()
        assert c.state == ControllerState.RECOVERING

        c.complete_recovery()
        assert c.state == ControllerState.NORMAL


class TestSirenAloneNeverGrantsGreen:
    """SAFETY: siren evidence alone must never grant priority."""

    def test_siren_suspected_cannot_skip_to_preparing(self):
        c = _make_controller()
        c.notify_siren_suspected("north")
        assert c.state == ControllerState.SUSPECTED
        # Can't jump to PREPARING from SUSPECTED
        with pytest.raises(SafetyViolation):
            c._transition(ControllerState.PREPARING, "siren alone")

    def test_siren_confirmed_cannot_skip_to_serving(self):
        c = _make_controller()
        _advance_to_confirmed(c)
        with pytest.raises(SafetyViolation):
            c._transition(ControllerState.SERVING, "siren alone")

    def test_request_priority_requires_confirmed_state(self):
        c = _make_controller()
        # Controller is NORMAL — request should fail
        now = 1000.0
        req = make_mock_request(approach="north", junction_id="J1", created_at=now, expiry_s=300.0)
        req.authorize(now=now)
        granted = c.request_priority(
            request_id=req.request_id,
            ambulance_id=req.ambulance_id,
            approach="north",
            expiry_at=req.expiry_at,
            confirmed_approach="north",
            now=now,
        )
        assert not granted
        assert c.state == ControllerState.NORMAL

    def test_siren_suspected_only_no_green(self):
        c = _make_controller()
        c.notify_siren_suspected("north")
        assert c.state == ControllerState.SUSPECTED
        # Cannot call execute_safe_transition_to_green from SUSPECTED
        with pytest.raises(SafetyViolation):
            c.execute_safe_transition_to_green()


class TestApproachMismatchRejection:
    def test_approach_mismatch_is_rejected(self):
        c = _make_controller()
        _advance_to_confirmed(c)
        now = 1000.0
        req = make_mock_request(approach="east", junction_id="J1", created_at=now, expiry_s=300.0)
        req.authorize(now=now)
        granted = c.request_priority(
            request_id=req.request_id,
            ambulance_id=req.ambulance_id,
            approach="east",
            expiry_at=req.expiry_at,
            confirmed_approach="north",  # audio says north, request says east
            now=now,
        )
        assert not granted
        assert c.state == ControllerState.CONFIRMED  # unchanged


class TestExpiredRequestRejection:
    def test_expired_request_is_rejected(self):
        c = _make_controller()
        _advance_to_confirmed(c)
        past = 1000.0
        req = make_mock_request(approach="north", junction_id="J1",
                                created_at=past - 400, expiry_s=10.0)
        granted = c.request_priority(
            request_id=req.request_id,
            ambulance_id=req.ambulance_id,
            approach="north",
            expiry_at=req.expiry_at,
            confirmed_approach="north",
            now=past,  # past > expiry_at
        )
        assert not granted


class TestPassageConfirmation:
    def test_passage_confirmed_by_vehicle_id(self):
        c = _make_controller()
        _advance_to_confirmed(c)
        now = 1000.0
        req = make_mock_request(approach="north", junction_id="J1", created_at=now, expiry_s=300.0)
        req.authorize(now=now)
        c.request_priority(
            request_id=req.request_id,
            ambulance_id=req.ambulance_id,
            approach="north",
            expiry_at=req.expiry_at,
            confirmed_approach="north",
            now=now,
        )
        c.execute_safe_transition_to_green(now=now)
        confirmed = c.confirm_passage(req.ambulance_id, now=now + 10)
        assert confirmed
        assert c.state == ControllerState.EXITING

    def test_wrong_vehicle_id_not_confirmed(self):
        c = _make_controller()
        _advance_to_confirmed(c)
        now = 1000.0
        req = make_mock_request(approach="north", junction_id="J1", created_at=now, expiry_s=300.0)
        req.authorize(now=now)
        c.request_priority(
            request_id=req.request_id,
            ambulance_id=req.ambulance_id,
            approach="north",
            expiry_at=req.expiry_at,
            confirmed_approach="north",
            now=now,
        )
        c.execute_safe_transition_to_green(now=now)
        confirmed = c.confirm_passage("WRONG-AMBULANCE", now=now + 10)
        assert not confirmed
        assert c.state == ControllerState.SERVING  # unchanged


class TestSafeExpiry:
    def test_expire_and_reset_returns_to_normal(self):
        c = _make_controller()
        _advance_to_confirmed(c)
        now = 1000.0
        req = make_mock_request(approach="north", junction_id="J1", created_at=now, expiry_s=300.0)
        req.authorize(now=now)
        c.request_priority(
            request_id=req.request_id,
            ambulance_id=req.ambulance_id,
            approach="north",
            expiry_at=req.expiry_at,
            confirmed_approach="north",
            now=now,
        )
        assert c.state == ControllerState.PREPARING
        c.expire_and_reset("simulated fault")
        assert c.state == ControllerState.NORMAL

    def test_check_request_expiry_triggers_on_timeout(self):
        c = _make_controller()
        _advance_to_confirmed(c)
        now = 1000.0
        req = make_mock_request(approach="north", junction_id="J1",
                                created_at=now, expiry_s=30.0)
        req.authorize(now=now)
        c.request_priority(
            request_id=req.request_id,
            ambulance_id=req.ambulance_id,
            approach="north",
            expiry_at=req.expiry_at,
            confirmed_approach="north",
            now=now,
        )
        # 60s later, past the 30s expiry
        expired = c.check_request_expiry(now=now + 60)
        assert expired
        assert c.state == ControllerState.NORMAL

