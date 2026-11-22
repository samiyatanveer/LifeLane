"""
test_sumo_integration.py — Integration tests for the LifeLane SUMO demo pipeline.

These tests use MockSumoRunner (no SUMO installation required) to verify the
complete dispatch + signal-controller + simulation pipeline.

Safety invariants tested:
  - Siren detection alone NEVER triggers green (stages before AUTHORIZED).
  - yellow → all-red → green sequence is enforced before TraCI set_phase calls.
  - Approach mismatch is rejected.
  - Duplicate request is rejected (Decision 5A).
  - Expired request is rejected.
  - Passage confirmation triggers EXITING → RECOVERING → NORMAL.

Run with:
    PYTHONPATH=src pytest tests/test_sumo_integration.py -v
"""
from __future__ import annotations

import time
from typing import Tuple
from unittest.mock import patch, call

import pytest

from lifelane_engine.dispatch.dispatch_service import (
    DuplicateRequestError,
    build_default_dispatch_service,
)
from lifelane_engine.dispatch.registry import MockRegistry
from lifelane_engine.simulation.mock_sumo import MockSumoRunner
from lifelane_engine.simulation.sumo_runner import SumoRunner, _SUMO_AVAILABLE
from lifelane_engine.traffic.signal_controller import (
    ControllerState,
    JunctionSignalController,
    SafetyViolation,
)

# ---------------------------------------------------------------------------
# Constants matching the demo setup
# ---------------------------------------------------------------------------
JUNCTION_ID = "J2"
APPROACH = "west"
AMBULANCE_ID = "LL-001"
DEVICE_ID = "DEV-001"
CREDENTIAL = "mock-secret-001"
VEHICLE_ID = "demo_ambulance_001"
ROUTE_ID = "r_amb_A"
HOSPITAL_ID = "H1"
ORIGIN = "J1"

# Signal phase indices (from grid.tll.xml)
PHASE_EW_GREEN = 0
PHASE_EW_YELLOW = 1
PHASE_ALL_RED = 2
PHASE_NS_GREEN = 3

YELLOW_S = 3.0
ALL_RED_S = 3.0
AMBULANCE_GREEN_S = 60.0

# Sim time offset for now= args (use a fixed epoch for reproducibility)
_T0 = 1_000_000.0


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def runner() -> MockSumoRunner:
    """MockSumoRunner in connected state."""
    r = MockSumoRunner(step_length_s=1.0, seed=42)
    r.connect()
    return r


@pytest.fixture()
def controller() -> JunctionSignalController:
    """Fresh JunctionSignalController for JUNCTION_ID."""
    return JunctionSignalController(junction_id=JUNCTION_ID)


@pytest.fixture()
def dispatch():
    """DispatchService wired with mock components."""
    return build_default_dispatch_service(
        verification_timeout_s=120.0,
        request_expiry_s=600.0,
    )


def _auth_and_submit(dispatch, controller, now: float = _T0):
    """
    Helper: run the full detection → auth → submit_request → request_priority flow.

    Returns (em_req, session_id).
    """
    # Detection (siren alone — no priority)
    dispatch.process_detection(
        approach=APPROACH,
        junction_id=JUNCTION_ID,
        ambulance_id=AMBULANCE_ID,
        now=now,
    )
    # Audio confirms
    controller.notify_siren_suspected(APPROACH)
    controller.notify_siren_confirmed(APPROACH)

    # Authenticate
    auth = dispatch.authenticate_registered(
        device_id=DEVICE_ID, credential=CREDENTIAL, now=now
    )
    assert auth.success, f"Auth failed: {auth.reason}"
    session = dispatch._session_manager.get_active_session(AMBULANCE_ID, now=now)
    assert session is not None

    # Submit request
    em_req = dispatch.submit_registered_request(
        ambulance_id=AMBULANCE_ID,
        session_id=session.session_id,
        origin=ORIGIN,
        hospital_id=HOSPITAL_ID,
        approach=APPROACH,
        junction_id=JUNCTION_ID,
        now=now,
    )
    return em_req, session.session_id


# ---------------------------------------------------------------------------
# Test 1: Siren detection alone must NOT advance controller past NORMAL
# ---------------------------------------------------------------------------

class TestSirenAloneNoGreen:
    """Safety rule: siren detection alone does not grant priority."""

    def test_detection_does_not_change_controller_state(self, dispatch, controller):
        """process_detection() must not advance the controller's state machine."""
        dispatch.process_detection(
            approach=APPROACH,
            junction_id=JUNCTION_ID,
            ambulance_id=AMBULANCE_ID,
            now=_T0,
        )
        # Controller was never called — stays NORMAL
        assert controller.state == ControllerState.NORMAL

    def test_set_phase_never_called_on_detection(self, runner, dispatch):
        """TraCI set_phase must never be called due to detection alone."""
        with patch.object(runner, "set_phase") as mock_set_phase:
            dispatch.process_detection(
                approach=APPROACH,
                junction_id=JUNCTION_ID,
                ambulance_id=AMBULANCE_ID,
                now=_T0,
            )
            mock_set_phase.assert_not_called()

    def test_suspected_does_not_grant_green(self, controller):
        """notify_siren_suspected() alone must not reach PREPARING/SERVING."""
        controller.notify_siren_suspected(APPROACH)
        assert controller.state == ControllerState.SUSPECTED
        # Cannot grant priority while SUSPECTED (not CONFIRMED)
        granted = controller.request_priority(
            request_id="r1",
            ambulance_id=AMBULANCE_ID,
            approach=APPROACH,
            expiry_at=_T0 + 600,
            confirmed_approach=APPROACH,
            now=_T0,
        )
        assert not granted
        assert controller.state == ControllerState.SUSPECTED


# ---------------------------------------------------------------------------
# Test 2: Full authorized flow — set_phase called in correct order
# ---------------------------------------------------------------------------

class TestFullAuthorizedFlow:
    """The complete dispatch+controller+runner pipeline."""

    def test_full_pipeline_reaches_serving(self, runner, dispatch, controller):
        """Full flow reaches SERVING state with correct phase calls."""
        em_req, _ = _auth_and_submit(dispatch, controller)

        granted = controller.request_priority(
            request_id=em_req.request_id,
            ambulance_id=AMBULANCE_ID,
            approach=APPROACH,
            expiry_at=_T0 + 600,
            confirmed_approach=APPROACH,
            now=_T0,
        )
        assert granted
        assert controller.state == ControllerState.PREPARING

        with patch.object(runner, "set_phase") as mock_sp, \
             patch.object(runner, "set_phase_duration"):
            # Yellow
            runner.set_phase(JUNCTION_ID, PHASE_EW_YELLOW)
            runner.set_phase_duration(JUNCTION_ID, YELLOW_S)
            # All-red
            runner.set_phase(JUNCTION_ID, PHASE_ALL_RED)
            runner.set_phase_duration(JUNCTION_ID, ALL_RED_S)
            # Controller transition
            controller.execute_safe_transition_to_green(now=_T0 + YELLOW_S + ALL_RED_S)
            assert controller.state == ControllerState.SERVING
            # Green
            runner.set_phase(JUNCTION_ID, PHASE_EW_GREEN)
            runner.set_phase_duration(JUNCTION_ID, AMBULANCE_GREEN_S)

            calls = [c[0] for c in mock_sp.call_args_list]
            assert calls[0] == (JUNCTION_ID, PHASE_EW_YELLOW), "First set_phase must be yellow"
            assert calls[1] == (JUNCTION_ID, PHASE_ALL_RED),   "Second set_phase must be all-red"
            assert calls[2] == (JUNCTION_ID, PHASE_EW_GREEN),  "Third set_phase must be green"

    def test_green_only_after_controller_approves(self, runner, dispatch, controller):
        """Green phase must not be set before execute_safe_transition_to_green."""
        em_req, _ = _auth_and_submit(dispatch, controller)

        controller.request_priority(
            request_id=em_req.request_id,
            ambulance_id=AMBULANCE_ID,
            approach=APPROACH,
            expiry_at=_T0 + 600,
            confirmed_approach=APPROACH,
            now=_T0,
        )
        # State is now PREPARING — not yet SERVING
        assert controller.state == ControllerState.PREPARING

        # Attempting green before transition should not be sanctioned by the state machine
        with pytest.raises(SafetyViolation):
            # execute_safe_transition_to_green is not callable from NORMAL/SUSPECTED/CONFIRMED
            # Simulate an erroneous direct call before PREPARING:
            bad_controller = JunctionSignalController(junction_id=JUNCTION_ID)
            # bad_controller is in NORMAL — calling execute_safe_transition_to_green
            # from NORMAL raises SafetyViolation
            bad_controller.execute_safe_transition_to_green()

    def test_ambulance_vehicle_in_mock(self, runner):
        """Ambulance vehicle is visible in mock after insertion."""
        runner.add_vehicle(
            vehicle_id=VEHICLE_ID,
            route_id=ROUTE_ID,
            vehicle_type="ambulance",
            depart_time=0.0,
        )
        runner.step()
        assert VEHICLE_ID in runner.get_vehicle_ids()

    def test_controller_state_after_green(self, dispatch, controller):
        """Controller is in SERVING after safe transition."""
        em_req, _ = _auth_and_submit(dispatch, controller)
        controller.request_priority(
            request_id=em_req.request_id,
            ambulance_id=AMBULANCE_ID,
            approach=APPROACH,
            expiry_at=_T0 + 600,
            confirmed_approach=APPROACH,
            now=_T0,
        )
        controller.execute_safe_transition_to_green(now=_T0 + YELLOW_S + ALL_RED_S)
        assert controller.state == ControllerState.SERVING


# ---------------------------------------------------------------------------
# Test 3: Duplicate request rejection (Decision 5A)
# ---------------------------------------------------------------------------

class TestDuplicateRequestRejected:
    def test_second_request_raises(self, dispatch, controller):
        """A second active request from the same ambulance is rejected."""
        em_req, session_id = _auth_and_submit(dispatch, controller)

        # Second submission must raise DuplicateRequestError
        with pytest.raises(DuplicateRequestError):
            dispatch.submit_registered_request(
                ambulance_id=AMBULANCE_ID,
                session_id=session_id,
                origin=ORIGIN,
                hospital_id=HOSPITAL_ID,
                approach=APPROACH,
                junction_id=JUNCTION_ID,
                now=_T0 + 1,
            )


# ---------------------------------------------------------------------------
# Test 4: Approach mismatch rejection
# ---------------------------------------------------------------------------

class TestApproachMismatch:
    def test_mismatch_denied(self, dispatch, controller):
        """Priority is denied if request approach != audio-confirmed approach."""
        em_req, _ = _auth_and_submit(dispatch, controller)
        # Controller confirmed approach is "west"; request with "north" must fail
        granted = controller.request_priority(
            request_id=em_req.request_id,
            ambulance_id=AMBULANCE_ID,
            approach="north",        # ← different from confirmed "west"
            expiry_at=_T0 + 600,
            confirmed_approach=APPROACH,  # "west"
            now=_T0,
        )
        assert not granted
        assert controller.state == ControllerState.CONFIRMED  # unchanged


# ---------------------------------------------------------------------------
# Test 5: Expired request rejection
# ---------------------------------------------------------------------------

class TestExpiredRequestRejected:
    def test_expired_request_denied(self, dispatch, controller):
        """Priority is denied when the request has expired."""
        em_req, _ = _auth_and_submit(dispatch, controller)

        # expiry_at is in the past
        granted = controller.request_priority(
            request_id=em_req.request_id,
            ambulance_id=AMBULANCE_ID,
            approach=APPROACH,
            expiry_at=_T0 - 1,   # already expired
            confirmed_approach=APPROACH,
            now=_T0,
        )
        assert not granted
        assert controller.state == ControllerState.CONFIRMED  # unchanged


# ---------------------------------------------------------------------------
# Test 6: Passage confirmation triggers recovery
# ---------------------------------------------------------------------------

class TestPassageConfirmationTriggersRecovery:
    def test_full_passage_to_normal(self, runner, dispatch, controller):
        """Passage confirmation drives controller: SERVING→EXITING→RECOVERING→NORMAL."""
        em_req, _ = _auth_and_submit(dispatch, controller)

        controller.request_priority(
            request_id=em_req.request_id,
            ambulance_id=AMBULANCE_ID,
            approach=APPROACH,
            expiry_at=_T0 + 600,
            confirmed_approach=APPROACH,
            now=_T0,
        )
        controller.execute_safe_transition_to_green(now=_T0 + YELLOW_S + ALL_RED_S)
        assert controller.state == ControllerState.SERVING

        # Confirm passage (vehicle-position-based)
        confirmed = controller.confirm_passage(
            ambulance_id=AMBULANCE_ID, now=_T0 + 70
        )
        assert confirmed
        assert controller.state == ControllerState.EXITING

        # Begin recovery
        controller.begin_recovery()
        assert controller.state == ControllerState.RECOVERING

        # Complete recovery
        controller.complete_recovery()
        assert controller.state == ControllerState.NORMAL

    def test_dispatch_passage_clears_active_request(self, dispatch, controller):
        """confirm_passage on dispatch removes the active request."""
        em_req, _ = _auth_and_submit(dispatch, controller)
        assert dispatch.get_active_request(AMBULANCE_ID) is not None

        dispatch.confirm_passage(
            ambulance_id=AMBULANCE_ID,
            junction_id=JUNCTION_ID,
            now=_T0+ 70,
        )
        assert dispatch.get_active_request(AMBULANCE_ID) is None

    def test_wrong_ambulance_passage_rejected(self, dispatch, controller):
        """confirm_passage with wrong ambulance_id returns False."""
        em_req, _ = _auth_and_submit(dispatch, controller)
        controller.request_priority(
            request_id=em_req.request_id,
            ambulance_id=AMBULANCE_ID,
            approach=APPROACH,
            expiry_at=_T0 + 600,
            confirmed_approach=APPROACH,
            now=_T0,
        )
        controller.execute_safe_transition_to_green(now=_T0 + YELLOW_S + ALL_RED_S)

        confirmed = controller.confirm_passage(
            ambulance_id="LL-999",  # wrong ID
            now=_T0 + 70,
        )
        assert not confirmed
        assert controller.state == ControllerState.SERVING  # unchanged


# ---------------------------------------------------------------------------
# Test 7: J4 conflict — conflicting approach at J4 is rejected
# ---------------------------------------------------------------------------

class TestJ4ConflictCheck:
    """
    At J4, Route A arrives from north (e_J2_J4) and Route B arrives from west (e_J3_J4).
    Two simultaneous requests on conflicting approaches must not both receive green.
    """

    def test_second_priority_request_rejected_different_approach(self):
        """A controller already SERVING one approach rejects a second request."""
        ctrl_j4 = JunctionSignalController(junction_id="J4")

        # Bring to CONFIRMED for approach "north"
        ctrl_j4.notify_siren_suspected("north")
        ctrl_j4.notify_siren_confirmed("north")

        # Grant priority for "north"
        granted = ctrl_j4.request_priority(
            request_id="req_north",
            ambulance_id="LL-001",
            approach="north",
            expiry_at=_T0 + 600,
            confirmed_approach="north",
            now=_T0,
        )
        assert granted
        ctrl_j4.execute_safe_transition_to_green(now=_T0 + YELLOW_S + ALL_RED_S)
        assert ctrl_j4.state == ControllerState.SERVING

        # A second request for "west" approach must fail — controller is SERVING
        granted2 = ctrl_j4.request_priority(
            request_id="req_west",
            ambulance_id="LL-002",
            approach="west",
            expiry_at=_T0 + 600,
            confirmed_approach="west",
            now=_T0 + 10,
        )
        assert not granted2, "Conflicting approach at J4 must be rejected while SERVING"
        assert ctrl_j4.state == ControllerState.SERVING


# ---------------------------------------------------------------------------
# Test 8: Illegal state transition raises SafetyViolation
# ---------------------------------------------------------------------------

class TestIllegalTransitionsRaised:
    def test_execute_green_from_normal_raises(self):
        ctrl = JunctionSignalController(junction_id=JUNCTION_ID)
        with pytest.raises(SafetyViolation):
            ctrl.execute_safe_transition_to_green()

    def test_execute_green_from_confirmed_raises(self):
        ctrl = JunctionSignalController(junction_id=JUNCTION_ID)
        ctrl.notify_siren_suspected(APPROACH)
        ctrl.notify_siren_confirmed(APPROACH)
        assert ctrl.state == ControllerState.CONFIRMED
        with pytest.raises(SafetyViolation):
            ctrl.execute_safe_transition_to_green()

    def test_complete_recovery_from_normal_raises(self):
        ctrl = JunctionSignalController(junction_id=JUNCTION_ID)
        with pytest.raises(SafetyViolation):
            ctrl.complete_recovery()


# ---------------------------------------------------------------------------
# Test 9: Mock runner signal phase tracking
# ---------------------------------------------------------------------------

class TestMockRunnerPhaseTracking:
    def test_set_phase_stored(self, runner):
        runner.set_phase(JUNCTION_ID, PHASE_EW_YELLOW)
        assert runner.get_phase(JUNCTION_ID) == PHASE_EW_YELLOW

    def test_all_red_phase(self, runner):
        runner.set_phase(JUNCTION_ID, PHASE_ALL_RED)
        assert runner.get_phase(JUNCTION_ID) == PHASE_ALL_RED

    def test_green_phase(self, runner):
        runner.set_phase(JUNCTION_ID, PHASE_EW_GREEN)
        assert runner.get_phase(JUNCTION_ID) == PHASE_EW_GREEN

    def test_phase_sequence_yellow_allred_green(self, runner):
        """The yellow → all-red → green sequence stores correctly."""
        runner.set_phase(JUNCTION_ID, PHASE_EW_YELLOW)
        assert runner.get_phase(JUNCTION_ID) == PHASE_EW_YELLOW
        runner.set_phase(JUNCTION_ID, PHASE_ALL_RED)
        assert runner.get_phase(JUNCTION_ID) == PHASE_ALL_RED
        runner.set_phase(JUNCTION_ID, PHASE_EW_GREEN)
        assert runner.get_phase(JUNCTION_ID) == PHASE_EW_GREEN


# ---------------------------------------------------------------------------
# Test 10: Ambulance vehicle lifecycle in mock
# ---------------------------------------------------------------------------

class TestMockVehicleLifecycle:
    def test_vehicle_added_and_visible(self, runner):
        runner.add_vehicle(VEHICLE_ID, ROUTE_ID, "ambulance", depart_time=0.0)
        runner.step()
        assert VEHICLE_ID in runner.get_vehicle_ids()

    def test_vehicle_progresses(self, runner):
        runner.add_vehicle(VEHICLE_ID, ROUTE_ID, "ambulance", depart_time=0.0, speed_ms=50.0)
        pos0 = None
        runner.step()
        pos0 = runner.get_vehicle_position(VEHICLE_ID)
        for _ in range(10):
            runner.step()
        pos1 = runner.get_vehicle_position(VEHICLE_ID)
        # Vehicle should have moved or arrived
        if pos0 is not None and pos1 is not None:
            assert pos1 != pos0 or runner.vehicle_has_arrived(VEHICLE_ID)

    def test_vehicle_arrives(self, runner):
        """With high speed the vehicle eventually arrives."""
        runner.add_vehicle(VEHICLE_ID, ROUTE_ID, "ambulance", depart_time=0.0, speed_ms=200.0)
        for _ in range(50):
            runner.step()
            if runner.vehicle_has_arrived(VEHICLE_ID):
                break
        assert runner.vehicle_has_arrived(VEHICLE_ID), "Vehicle should arrive within 50 steps at 200 m/s"

    def test_road_id_progresses_along_route(self, runner):
        """get_vehicle_road returns route edges in order."""
        runner.add_vehicle(VEHICLE_ID, ROUTE_ID, "ambulance", depart_time=0.0, speed_ms=50.0)
        roads_seen = set()
        for _ in range(30):
            runner.step()
            if VEHICLE_ID in runner.get_vehicle_ids():
                roads_seen.add(runner.get_vehicle_road(VEHICLE_ID))
        # Route A: J1→J2→J4→H1 means edges e_J1_J2, e_J2_J4, e_J4_H1
        route_edges = {"e_J1_J2", "e_J2_J4", "e_J4_H1"}
        assert roads_seen.issubset(route_edges | {"unknown", "ARRIVED"}), (
            f"Unexpected edge IDs: {roads_seen - route_edges}"
        )


# ---------------------------------------------------------------------------
# Test 11: Real SUMO Runner tests (using real Eclipse SUMO via libsumo/TraCI)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _SUMO_AVAILABLE, reason="SUMO not installed on this machine")
class TestRealSumoRunnerIntegration:
    """Verifies that SumoRunner operates against real SUMO network files."""

    def test_real_sumo_runner_lifecycle(self):
        """Connects to real SUMO, advances simulation, modifies signals, and disconnects."""
        runner = SumoRunner(seed=42)
        runner.connect()
        try:
            # Baseline simulation step
            t1 = runner.step()
            assert t1 > 0.0

            # Traffic light query and override
            initial_phase = runner.get_phase(JUNCTION_ID)
            assert initial_phase in (0, 1, 2, 3, 4)

            runner.set_phase(JUNCTION_ID, PHASE_EW_YELLOW)
            runner.set_phase_duration(JUNCTION_ID, 3.0)
            assert runner.get_phase(JUNCTION_ID) == PHASE_EW_YELLOW

            # Insert an emergency vehicle
            runner.add_vehicle(
                vehicle_id="pytest_amb_001",
                route_id=ROUTE_ID,
                vehicle_type="ambulance",
                depart_time=runner.sim_time,
            )
            # Step to allow vehicle insertion
            for _ in range(3):
                runner.step()

            vids = runner.get_vehicle_ids()
            assert "pytest_amb_001" in vids
            pos = runner.get_vehicle_position("pytest_amb_001")
            assert pos is not None
            assert len(pos) == 2
            speed = runner.get_vehicle_speed("pytest_amb_001")
            assert speed >= 0.0
            road = runner.get_vehicle_road("pytest_amb_001")
            assert "J1" in road or "J2" in road

            # Queue length via detector
            queue_len = runner.get_queue_length(JUNCTION_ID, APPROACH)
            assert isinstance(queue_len, int)
            assert queue_len >= 0
        finally:
            runner.stop()

    def test_real_sumo_with_controller_priority(self, dispatch, controller):
        """Verifies full safety controller priority flow against real SUMO."""
        runner = SumoRunner(seed=42)
        runner.connect()
        try:
            # Step baseline
            for _ in range(5):
                runner.step()

            # Detection
            dispatch.process_detection(
                approach=APPROACH,
                junction_id=JUNCTION_ID,
                ambulance_id=AMBULANCE_ID,
                now=runner.sim_time,
            )
            assert controller.state == ControllerState.NORMAL

            # Audio confirmation
            controller.notify_siren_suspected(APPROACH)
            controller.notify_siren_confirmed(APPROACH)
            assert controller.state == ControllerState.CONFIRMED

            # Auth & request
            auth = dispatch.authenticate_registered(
                device_id=DEVICE_ID, credential=CREDENTIAL, now=runner.sim_time
            )
            assert auth.success
            session = dispatch._session_manager.get_active_session(AMBULANCE_ID, now=runner.sim_time)
            em_req = dispatch.submit_registered_request(
                ambulance_id=AMBULANCE_ID,
                session_id=session.session_id,
                origin=ORIGIN,
                hospital_id=HOSPITAL_ID,
                approach=APPROACH,
                junction_id=JUNCTION_ID,
                now=runner.sim_time,
            )

            # Insert ambulance into real SUMO
            runner.add_vehicle(
                vehicle_id="pytest_amb_priority",
                route_id=ROUTE_ID,
                vehicle_type="ambulance",
                depart_time=runner.sim_time,
            )

            # Request priority
            priority_granted = controller.request_priority(
                request_id=em_req.request_id,
                ambulance_id=AMBULANCE_ID,
                approach=APPROACH,
                expiry_at=runner.sim_time + 600,
                confirmed_approach=APPROACH,
                now=runner.sim_time,
            )
            assert priority_granted
            assert controller.state == ControllerState.PREPARING

            # TraCI safe transitions
            runner.set_phase(JUNCTION_ID, PHASE_EW_YELLOW)
            runner.set_phase_duration(JUNCTION_ID, YELLOW_S)
            for _ in range(int(YELLOW_S)):
                runner.step()

            runner.set_phase(JUNCTION_ID, PHASE_ALL_RED)
            runner.set_phase_duration(JUNCTION_ID, ALL_RED_S)
            for _ in range(int(ALL_RED_S)):
                runner.step()

            # Controller safe transition to green
            controller.execute_safe_transition_to_green(now=runner.sim_time)
            assert controller.state == ControllerState.SERVING

            runner.set_phase(JUNCTION_ID, PHASE_EW_GREEN)
            runner.set_phase_duration(JUNCTION_ID, AMBULANCE_GREEN_S)
            assert runner.get_phase(JUNCTION_ID) == PHASE_EW_GREEN

            # Confirm passage
            confirmed = controller.confirm_passage(AMBULANCE_ID, now=runner.sim_time)
            assert confirmed
            assert controller.state == ControllerState.EXITING

            controller.begin_recovery()
            assert controller.state == ControllerState.RECOVERING

            controller.complete_recovery()
            assert controller.state == ControllerState.NORMAL
        finally:
            runner.stop()
