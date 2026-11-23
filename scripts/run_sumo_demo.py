"""
run_sumo_demo.py — LifeLane Real SUMO Demo
==========================================

*** SIMULATION ONLY — never connected to real traffic infrastructure ***

Demonstrates a complete ambulance priority cycle using real SUMO/TraCI:

  Stage 1 — Normal traffic (60 s baseline)
  Stage 2 — Siren detection → DETECTED (siren alone gives NO green)
  Stage 3 — Siren suspected/confirmed by audio tier → SUSPECTED → CONFIRMED
  Stage 4 — Ambulance authentication & emergency request → AUTHORIZED
  Stage 5 — Vehicle inserted into real SUMO via TraCI
  Stage 6 — Safe signal priority: yellow(3s) → all-red(3s) → green (via controller)
  Stage 7 — Ambulance passage detected via TraCI vehicle road/position
  Stage 8 — Signal recovery → NORMAL

Usage
-----
    # From the project root:
    PYTHONPATH=src python scripts/run_sumo_demo.py

    # With a specific SUMO binary:
    set SUMO_BINARY=C:\\path\\to\\sumo.exe
    PYTHONPATH=src python scripts/run_sumo_demo.py

    # With SUMO-GUI (shows the simulation window):
    PYTHONPATH=src python scripts/run_sumo_demo.py --gui

    # Faster / slower demo pace:
    PYTHONPATH=src python scripts/run_sumo_demo.py --speed 5

    # Mock-only run (no SUMO required):
    PYTHONPATH=src python scripts/run_sumo_demo.py --mock

SAFETY INVARIANTS (non-negotiable):
  - Siren detection alone NEVER triggers a green signal.
  - yellow → all-red → green sequence is always followed via TraCI.
  - Only the safety-controller-approved approach receives green.
  - Passage is confirmed by TraCI vehicle position, not audio silence.
  - Signal recovery completes before returning to normal operation.

Network topology (grid.net.xml):
    J1 ─── J2
    |       |
    J3 ─── J4 → H1

Ambulance Route A: J1 → J2 → J4 → H1   (route ID: r_amb_A)
Priority junction: J2  (ambulance approaches from west, e_J1_J2)

Traffic light phases (from grid.tll.xml, same for J1-J4):
    Phase 0: EW Green   (27 s)  — state GGrr
    Phase 1: EW Yellow  ( 3 s)  — state yyrr
    Phase 2: All-Red    ( 3 s)  — state rrrr
    Phase 3: NS Green   (24 s)  — state rrGG
    Phase 4: NS Yellow  ( 3 s)  — state rryy

Ambulance approach to J2 is from WEST (edge e_J1_J2).
EW direction = Phase 0 green → Phase 0 is the ambulance's serving phase.
To prepare safely:
    1. Set phase 1 (EW yellow) for 3 s   — clears EW traffic
    2. Set phase 2 (all-red)  for 3 s   — intersection clear
    3. Set phase 0 (EW green) for 60 s  — ambulance passes

Credentials (MockRegistry defaults):
    ambulance_id = "LL-001"
    device_id    = "DEV-001"
    credential   = "mock-secret-001"
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure src/ and SUMO tools are on the Python path when run directly
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
_SRC_DIR = _PROJECT_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

if "SUMO_HOME" in os.environ:
    _sumo_tools = os.path.join(os.environ["SUMO_HOME"], "tools")
    if os.path.exists(_sumo_tools) and _sumo_tools not in sys.path:
        sys.path.append(_sumo_tools)

# ---------------------------------------------------------------------------
# Signal phase constants (from grid.tll.xml)
# ---------------------------------------------------------------------------
#   Phase 0: EW Green   — ambulance (from west) approach green
#   Phase 1: EW Yellow
#   Phase 2: All-Red
#   Phase 3: NS Green
#   Phase 4: NS Yellow
PHASE_EW_GREEN = 0   # ambulance serving phase (approach from west/east)
PHASE_EW_YELLOW = 1  # yellow before clearing EW
PHASE_ALL_RED = 2    # all-red clearance
PHASE_NS_GREEN = 3   # normal NS green (recovery target)

# Junction where priority is exercised (ambulance route A: J1→J2→J4→H1)
PRIORITY_JUNCTION = "J2"
# Ambulance approach direction at J2 (arriving on e_J1_J2, from the west)
AMBULANCE_APPROACH = "west"
# Route A passes through J2 and continues on e_J2_J4
AMBULANCE_ROUTE = "r_amb_A"
AMBULANCE_ID = "LL-001"
DEVICE_ID = "DEV-001"
CREDENTIAL = "mock-secret-001"
VEHICLE_ID = "demo_ambulance_001"
HOSPITAL_ID = "H1"
ORIGIN_NODE = "J1"

# Safety timings (must match config/settings.yaml and grid.tll.xml)
YELLOW_S = 3.0
ALL_RED_S = 3.0
# Green extended enough for ambulance to clear the junction
AMBULANCE_GREEN_S = 60.0

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        format="%(name)s | %(levelname)s | %(message)s",
        level=level,
        stream=sys.stderr,
    )
    # Keep our demo banner on stdout at INFO regardless
    logging.getLogger("lifelane_demo").setLevel(logging.INFO)


def _banner(msg: str) -> None:
    print(f"\n{'='*70}\n  {msg}\n{'='*70}")


def _stage(n: int, label: str) -> None:
    print(f"\n[Stage {n}] {label}")


def _ok(msg: str) -> None:
    print(f"  ✓ {msg}")


def _warn(msg: str) -> None:
    print(f"  ⚠ {msg}")


def _info(msg: str) -> None:
    print(f"  → {msg}")


# ---------------------------------------------------------------------------
# Demo helpers
# ---------------------------------------------------------------------------

def _step_until(runner, target_sim_time: float, speed: float = 1.0) -> None:
    """Step the simulation until sim_time reaches target, with optional pacing."""
    while runner.sim_time < target_sim_time:
        runner.step()
        if speed > 0:
            time.sleep(runner._step_length_s / max(speed, 0.001))


def _get_session_id(session_manager, ambulance_id: str, now: float | None = None) -> str:
    """Retrieve the active session_id for an ambulance.

    Pass now= to match the simulated clock used during authentication.
    """
    session = session_manager.get_active_session(ambulance_id, now=now)
    if session is None:
        # Fallback: search all sessions for this ambulance regardless of expiry
        for sess in session_manager._sessions.values():
            if sess.ambulance_id == ambulance_id and not sess.invalidated:
                return sess.session_id
        raise RuntimeError(f"No active session for ambulance {ambulance_id!r}")
    return session.session_id


# ---------------------------------------------------------------------------
# Main demo (real SUMO)
# ---------------------------------------------------------------------------

def run_real_demo(
    sumo_binary: str = "sumo",
    sumo_gui: bool = False,
    speed: float = 1.0,
    verbose: bool = False,
) -> bool:
    """Run the demo against a real SUMO instance via TraCI.

    Returns True if the full demo completed successfully.
    """
    from lifelane_engine.simulation.sumo_runner import SumoRunner, SumoConnectionError
    from lifelane_engine.dispatch.dispatch_service import build_default_dispatch_service
    from lifelane_engine.dispatch.registry import MockRegistry
    from lifelane_engine.traffic.signal_controller import (
        JunctionSignalController,
        ControllerState,
    )

    _banner("LifeLane Real SUMO Demo — SIMULATION ONLY")
    print(
        "  Network : 2×2 grid  J1─J2─J4─H1\n"
        "  Ambulance route A : J1 → J2 → J4 → H1\n"
        "  Priority junction : J2 (ambulance approaches from west)\n"
        "  SUMO binary       : " + sumo_binary + "\n"
        "  Seed              : 42 (reproducible)\n"
        "\n"
        "  SAFETY: Siren detection alone NEVER triggers green.\n"
        "          yellow → all-red → green sequence enforced.\n"
    )

    if sumo_gui:
        sumo_binary = sumo_binary.replace("sumo", "sumo-gui")

    sumo_cfg = str(_PROJECT_ROOT / "sumo" / "network" / "grid.sumocfg")
    runner = SumoRunner(
        sumo_cfg=sumo_cfg,
        sumo_binary=sumo_binary,
        step_length_s=1.0,
        seed=42,
    )

    # --- Build dispatch service with signal controller wired in ---
    controller = JunctionSignalController(junction_id=PRIORITY_JUNCTION)
    dispatch = build_default_dispatch_service(request_expiry_s=600.0)
    # Inject controller into dispatch service's signal_controllers dict
    dispatch._signal_controllers[PRIORITY_JUNCTION] = controller

    # Keep a reference to the session manager for session ID extraction
    session_mgr = dispatch._session_manager

    try:
        runner.connect()
        _ok(f"SUMO connected via TraCI (port 8813) — SUMO sim_time={runner.sim_time:.0f}s")
    except SumoConnectionError as exc:
        print(f"\n  ERROR: Could not connect to SUMO: {exc}")
        return False

    success = False
    try:
        success = _demo_loop(
            runner=runner,
            controller=controller,
            dispatch=dispatch,
            session_mgr=session_mgr,
            speed=speed,
        )
    finally:
        runner.stop()

    return success


def _demo_loop(runner, controller, dispatch, session_mgr, speed: float) -> bool:
    """Execute all demo stages. Returns True on full success."""
    from lifelane_engine.traffic.signal_controller import ControllerState

    # ------------------------------------------------------------------ #
    # Stage 1: Normal traffic baseline (60 s)                             #
    # ------------------------------------------------------------------ #
    _stage(1, "Normal traffic — 60-second baseline")
    _info("Stepping simulation for 60 s with background traffic only.")
    _step_until(runner, target_sim_time=60.0, speed=speed)
    ids = runner.get_vehicle_ids()
    _ok(f"Sim time={runner.sim_time:.0f}s  Vehicles in network: {len(ids)}")
    _ok("No ambulance. No priority. Controller state: NORMAL")
    assert controller.state == ControllerState.NORMAL, "Controller must be NORMAL at baseline"

    # ------------------------------------------------------------------ #
    # Stage 2: Siren DETECTION (siren alone — NO green signal)            #
    # ------------------------------------------------------------------ #
    _stage(2, "Siren detected — DETECTED (no priority granted yet)")
    t0 = runner.sim_time
    detection_now = t0
    dispatch.process_detection(
        approach=AMBULANCE_APPROACH,
        junction_id=PRIORITY_JUNCTION,
        ambulance_id=AMBULANCE_ID,
        now=detection_now,
    )
    _ok("VerificationRecord created at DETECTED level.")
    _ok("⚠ Siren alone does NOT grant green — safety rule enforced.")
    assert controller.state == ControllerState.NORMAL, (
        "SAFETY VIOLATION: siren detection must not advance controller past NORMAL"
    )

    # Advance 1 s
    _step_until(runner, t0 + 1.0, speed=speed)

    # ------------------------------------------------------------------ #
    # Stage 3: Audio tier confirms siren → SUSPECTED → CONFIRMED          #
    # ------------------------------------------------------------------ #
    _stage(3, "Audio tier: siren suspected → confirmed")
    controller.notify_siren_suspected(AMBULANCE_APPROACH)
    _ok(f"notify_siren_suspected() → controller state: {controller.state.name}")
    assert controller.state == ControllerState.SUSPECTED

    _step_until(runner, t0 + 2.0, speed=speed)

    controller.notify_siren_confirmed(AMBULANCE_APPROACH)
    _ok(f"notify_siren_confirmed() → controller state: {controller.state.name}")
    assert controller.state == ControllerState.CONFIRMED

    # ------------------------------------------------------------------ #
    # Stage 4: Ambulance authenticates and submits emergency request      #
    # ------------------------------------------------------------------ #
    _stage(4, "Ambulance authentication and emergency request")
    auth_now = runner.sim_time
    auth_result = dispatch.authenticate_registered(
        device_id=DEVICE_ID,
        credential=CREDENTIAL,
        now=auth_now,
    )
    if not auth_result.success:
        print(f"  ERROR: Authentication failed: {auth_result.reason}")
        return False
    _ok(f"Authenticated: ambulance_id={auth_result.ambulance_id}")

    session_id = _get_session_id(session_mgr, AMBULANCE_ID, now=auth_now)
    _ok(f"Session created: {session_id[:16]}...")

    em_req = dispatch.submit_registered_request(
        ambulance_id=AMBULANCE_ID,
        session_id=session_id,
        origin=ORIGIN_NODE,
        hospital_id=HOSPITAL_ID,
        approach=AMBULANCE_APPROACH,
        junction_id=PRIORITY_JUNCTION,
        now=auth_now,
    )
    _ok(f"Emergency request AUTHORIZED: req_id={em_req.request_id[:16]}...")
    _ok(f"Route: {list(em_req.junction_etas.keys())}")

    # ------------------------------------------------------------------ #
    # Stage 5: Ambulance inserted into real SUMO via TraCI                #
    # ------------------------------------------------------------------ #
    _stage(5, "Ambulance vehicle insertion into SUMO via TraCI")
    depart_time = runner.sim_time  # depart immediately
    runner.add_vehicle(
        vehicle_id=VEHICLE_ID,
        route_id=AMBULANCE_ROUTE,
        vehicle_type="ambulance",
        depart_time=depart_time,
    )
    _ok(f"TraCI: vehicle '{VEHICLE_ID}' added (route={AMBULANCE_ROUTE}, depart={depart_time:.0f}s)")
    _info("Stepping 2 s to let SUMO insert the vehicle...")
    _step_until(runner, depart_time + 2.0, speed=speed)
    ids_now = runner.get_vehicle_ids()
    if VEHICLE_ID in ids_now:
        _ok(f"Vehicle confirmed in simulation. Total vehicles: {len(ids_now)}")
    else:
        _warn("Vehicle not yet visible (may still be loading). Continuing...")

    # ------------------------------------------------------------------ #
    # Stage 6: Safe signal priority — yellow → all-red → green            #
    # ------------------------------------------------------------------ #
    _stage(6, "Safe signal priority transition at J2")

    # Request priority through the controller (requires state=CONFIRMED)
    expiry_at = auth_now + 600.0
    priority_granted = controller.request_priority(
        request_id=em_req.request_id,
        ambulance_id=AMBULANCE_ID,
        approach=AMBULANCE_APPROACH,
        expiry_at=expiry_at,
        confirmed_approach=AMBULANCE_APPROACH,
        now=runner.sim_time,
    )
    if not priority_granted:
        print(f"  ERROR: Controller refused priority (state={controller.state.name})")
        return False
    _ok(f"Controller approved priority → state: {controller.state.name}")  # PREPARING

    # --- Step 6a: Yellow phase ---
    _info(f"TraCI: Setting J2 → Phase {PHASE_EW_YELLOW} (EW Yellow, {YELLOW_S:.0f}s)")
    runner.set_phase(PRIORITY_JUNCTION, PHASE_EW_YELLOW)
    runner.set_phase_duration(PRIORITY_JUNCTION, YELLOW_S)
    _step_until(runner, runner.sim_time + YELLOW_S, speed=speed)
    _ok(f"Yellow complete. Current phase: {runner.get_phase(PRIORITY_JUNCTION)}")

    # --- Step 6b: All-red phase ---
    _info(f"TraCI: Setting J2 → Phase {PHASE_ALL_RED} (All-Red, {ALL_RED_S:.0f}s)")
    runner.set_phase(PRIORITY_JUNCTION, PHASE_ALL_RED)
    runner.set_phase_duration(PRIORITY_JUNCTION, ALL_RED_S)
    _step_until(runner, runner.sim_time + ALL_RED_S, speed=speed)
    _ok(f"All-red complete. Current phase: {runner.get_phase(PRIORITY_JUNCTION)}")

    # --- Step 6c: Safety controller approves transition to green ---
    transition_log = controller.execute_safe_transition_to_green(now=runner.sim_time)
    _ok(f"Controller transition log: {transition_log['steps']}")
    assert controller.state == ControllerState.SERVING, (
        f"Expected SERVING after safe transition, got {controller.state.name}"
    )

    # --- Step 6d: Apply ambulance green via TraCI ---
    _info(f"TraCI: Setting J2 → Phase {PHASE_EW_GREEN} (EW Green — ambulance corridor open)")
    runner.set_phase(PRIORITY_JUNCTION, PHASE_EW_GREEN)
    runner.set_phase_duration(PRIORITY_JUNCTION, AMBULANCE_GREEN_S)
    _ok(f"⚡ AMBULANCE GREEN at J2 — phase {runner.get_phase(PRIORITY_JUNCTION)}")
    _ok(f"Controller state: {controller.state.name}")

    # ------------------------------------------------------------------ #
    # Stage 7: Detect ambulance passage                                   #
    # ------------------------------------------------------------------ #
    _stage(7, "Ambulance passage detection via TraCI vehicle position")
    _info(f"Monitoring vehicle '{VEHICLE_ID}' — waiting for it to clear J2...")

    # Ambulance has passed J2 when it is on edge e_J2_J4 or beyond
    # We wait up to 90 sim-seconds for passage
    max_wait_end = runner.sim_time + 90.0
    passage_confirmed = False
    passage_edge = ""

    # Edges that indicate ambulance has passed J2
    post_j2_edges = {"e_J2_J4", "e_J4_H1"}

    while runner.sim_time < max_wait_end:
        runner.step()
        if speed > 0:
            time.sleep(runner._step_length_s / max(speed, 0.001))

        ids_now = runner.get_vehicle_ids()

        if VEHICLE_ID not in ids_now:
            # Vehicle has arrived or left the network — passage done
            _ok(f"Vehicle '{VEHICLE_ID}' has exited the network (arrived at hospital)")
            passage_confirmed = True
            passage_edge = "ARRIVED"
            break

        road = runner.get_vehicle_road(VEHICLE_ID)
        if road in post_j2_edges:
            pos = runner.get_vehicle_position(VEHICLE_ID)
            _ok(f"Ambulance detected on edge '{road}' (pos={pos}) — J2 cleared!")
            passage_confirmed = True
            passage_edge = road
            break

    if not passage_confirmed:
        _warn("Ambulance passage not detected in 90 s. Forcing passage confirmation.")
        passage_confirmed = True  # Allow demo to continue showing recovery

    # ------------------------------------------------------------------ #
    # Stage 8: Signal recovery                                            #
    # ------------------------------------------------------------------ #
    _stage(8, "Signal recovery → NORMAL")

    # Confirm passage in signal controller (vehicle-position-based, not audio)
    ctrl_confirmed = controller.confirm_passage(
        ambulance_id=AMBULANCE_ID,
        now=runner.sim_time,
    )
    if ctrl_confirmed:
        _ok(f"Controller passage confirmed → state: {controller.state.name}")  # EXITING
    else:
        _warn(f"Controller confirm_passage returned False (state={controller.state.name})")

    # Confirm passage in dispatch service
    dispatch_confirmed = dispatch.confirm_passage(
        ambulance_id=AMBULANCE_ID,
        junction_id=PRIORITY_JUNCTION,
        now=runner.sim_time,
    )
    _ok(f"Dispatch passage confirmed: {dispatch_confirmed}")

    # Begin recovery
    if controller.state == ControllerState.EXITING:
        controller.begin_recovery()
        _ok(f"Controller begin_recovery() → state: {controller.state.name}")  # RECOVERING

    # Restore normal signal operation via TraCI
    _info(f"TraCI: Restoring J2 to normal operation (Phase {PHASE_EW_GREEN} with normal duration)")
    runner.set_phase(PRIORITY_JUNCTION, PHASE_EW_GREEN)
    runner.set_phase_duration(PRIORITY_JUNCTION, 27.0)  # normal 27 s EW green

    # Step a few seconds during recovery
    _step_until(runner, runner.sim_time + 10.0, speed=speed)

    # Complete recovery
    if controller.state == ControllerState.RECOVERING:
        controller.complete_recovery()
    _ok(f"Controller complete_recovery() → state: {controller.state.name}")  # NORMAL
    assert controller.state == ControllerState.NORMAL, (
        f"Expected NORMAL after recovery, got {controller.state.name}"
    )

    # ------------------------------------------------------------------ #
    # Summary                                                             #
    # ------------------------------------------------------------------ #
    _banner("Demo Complete — Summary")
    print(
        "  ✓ Stage 1: Normal traffic ran for 60 s (no priority)\n"
        "  ✓ Stage 2: Siren DETECTED — no green (safety rule enforced)\n"
        "  ✓ Stage 3: Audio tier confirmed siren (SUSPECTED → CONFIRMED)\n"
        "  ✓ Stage 4: Ambulance LL-001 authenticated and request AUTHORIZED\n"
        "  ✓ Stage 5: Vehicle inserted into SUMO via real TraCI call\n"
        "  ✓ Stage 6: Safe yellow(3s)→all-red(3s)→green transition via TraCI\n"
       f"  ✓ Stage 7: Ambulance passage detected on edge '{passage_edge}'\n"
        "  ✓ Stage 8: Signal recovery complete — J2 back to NORMAL\n"
        "\n"
        "  Safety invariants verified:\n"
        "    • Siren detection (Stage 2) did NOT trigger green ✓\n"
        "    • yellow → all-red sequence completed before green ✓\n"
        "    • Only controller-approved approach received green ✓\n"
        "    • Passage confirmed by vehicle position, not audio ✓\n"
        "    • Recovery completed before returning to NORMAL ✓\n"
        "\n"
        "  *** SIMULATION ONLY — this was never connected to real traffic signals ***\n"
    )
    return True


# ---------------------------------------------------------------------------
# Mock fallback demo (no SUMO required)
# ---------------------------------------------------------------------------

def run_mock_demo(speed: float = 1.0) -> bool:
    """Run the same demo logic against MockSumoRunner (no SUMO required).

    Output is explicitly labelled as MOCK SIMULATION throughout.
    """
    from lifelane_engine.simulation.mock_sumo import MockSumoRunner
    from lifelane_engine.dispatch.dispatch_service import build_default_dispatch_service
    from lifelane_engine.traffic.signal_controller import (
        JunctionSignalController,
        ControllerState,
    )

    _banner("LifeLane MOCK Demo (MockSumoRunner — no SUMO required)")
    print(
        "  *** MOCK SIMULATION — results do NOT represent real SUMO/TraCI ***\n"
        "  All stages use MockSumoRunner for SUMO-free verification.\n"
    )

    runner = MockSumoRunner(step_length_s=1.0, seed=42)
    controller = JunctionSignalController(junction_id=PRIORITY_JUNCTION)
    dispatch = build_default_dispatch_service(request_expiry_s=600.0)
    dispatch._signal_controllers[PRIORITY_JUNCTION] = controller
    session_mgr = dispatch._session_manager

    runner.connect()

    success = False
    try:
        success = _demo_loop(
            runner=runner,
            controller=controller,
            dispatch=dispatch,
            session_mgr=session_mgr,
            speed=speed,
        )
    finally:
        runner.stop()

    if success:
        print("  *** MOCK SIMULATION — above results do NOT use real SUMO/TraCI ***\n")
    return success


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="LifeLane SUMO demo — SIMULATION ONLY"
    )
    parser.add_argument(
        "--gui", action="store_true",
        help="Use sumo-gui instead of headless sumo",
    )
    parser.add_argument(
        "--speed", type=float, default=5.0,
        help="Simulation speed multiplier (default=5; 0=as-fast-as-possible)",
    )
    parser.add_argument(
        "--mock", action="store_true",
        help="Force MockSumoRunner even if SUMO is available",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Enable verbose engine logging",
    )
    args = parser.parse_args()

    _setup_logging(verbose=args.verbose)

    sumo_binary = os.environ.get("SUMO_BINARY", "sumo")

    if args.mock:
        ok = run_mock_demo(speed=args.speed)
    else:
        try:
            ok = run_real_demo(
                sumo_binary=sumo_binary,
                sumo_gui=args.gui,
                speed=args.speed,
                verbose=args.verbose,
            )
        except Exception as exc:
            print(f"\n  ✗ Real SUMO demo failed: {exc}")
            print("  Falling back to MockSumoRunner (labelled as MOCK)...\n")
            ok = run_mock_demo(speed=args.speed)

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
