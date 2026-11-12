"""
sumo_runner.py — SUMO/TraCI integration for LifeLane Phase 3.

Connects to a running SUMO instance via TraCI, steps the simulation,
reads vehicle positions (feeding them into GpsTracker as SIMULATED updates),
and applies signal phase overrides from the safety controller.

Falls back gracefully to MockSumoRunner if SUMO is not installed.

SAFETY RULE: All signal overrides go through JunctionSignalController's
             state machine. This module NEVER bypasses safety checks.

*** SIMULATION ONLY — never connected to real traffic signals ***
"""
from __future__ import annotations

import logging
import os
import subprocess
import time
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Attempt TraCI import; fall back to None if SUMO not installed
try:
    import traci  # type: ignore
    import traci.constants as tc  # type: ignore
    _TRACI_AVAILABLE = True
    logger.info("[sumo_runner] TraCI imported successfully")
except ImportError:
    traci = None  # type: ignore
    tc = None     # type: ignore
    _TRACI_AVAILABLE = False
    logger.warning(
        "[sumo_runner] TraCI not available — use MockSumoRunner for testing"
    )

# Project-relative paths
_PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")
)
DEFAULT_SUMO_CFG = os.path.join(_PROJECT_ROOT, "sumo", "network", "grid.sumocfg")
DEFAULT_SUMO_BINARY = os.environ.get("SUMO_BINARY", "sumo")
DEFAULT_TRACI_PORT = 8813


class SumoConnectionError(RuntimeError):
    """Raised when SUMO/TraCI connection cannot be established."""


class SumoRunner:
    """Wraps a SUMO simulation via TraCI.

    Args:
        sumo_cfg:      Path to the .sumocfg configuration file.
        sumo_binary:   Path to the sumo (or sumo-gui) executable.
        port:          TraCI port number.
        step_length_s: Simulation step length in seconds.
        seed:          Random seed for SUMO (reproducibility).
    """

    def __init__(
        self,
        sumo_cfg: str = DEFAULT_SUMO_CFG,
        sumo_binary: str = DEFAULT_SUMO_BINARY,
        port: int = DEFAULT_TRACI_PORT,
        step_length_s: float = 1.0,
        seed: int = 42,
    ) -> None:
        if not _TRACI_AVAILABLE:
            raise SumoConnectionError(
                "TraCI is not installed. Install SUMO via "
                "'pip install eclipse-sumo' or from https://sumo.dlr.de, "
                "then set SUMO_HOME. Use MockSumoRunner for SUMO-free testing."
            )
        self._sumo_cfg = sumo_cfg
        self._sumo_binary = sumo_binary
        self._port = port
        self._step_length_s = step_length_s
        self._seed = seed
        self._sim_time: float = 0.0
        self._connected: bool = False
        self._sumo_proc: Optional[subprocess.Popen] = None

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Launch SUMO and open a TraCI connection.

        Raises:
            SumoConnectionError: if SUMO executable not found or TraCI fails.
        """
        sumo_cmd = [
            self._sumo_binary,
            "-c", self._sumo_cfg,
            "--remote-port", str(self._port),
            "--seed", str(self._seed),
            "--no-step-log", "true",
            "--no-warnings", "true",
        ]
        logger.info("[sumo_runner] Starting SUMO: %s", " ".join(sumo_cmd))
        try:
            self._sumo_proc = subprocess.Popen(
                sumo_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError as exc:
            raise SumoConnectionError(
                f"SUMO binary '{self._sumo_binary}' not found. "
                "Install SUMO or set SUMO_BINARY environment variable."
            ) from exc

        # Give SUMO time to start
        time.sleep(1.5)
        try:
            traci.init(port=self._port)
        except Exception as exc:
            self.stop()
            raise SumoConnectionError(f"TraCI connection failed: {exc}") from exc

        self._connected = True
        self._sim_time = 0.0
        logger.info("[sumo_runner] Connected via TraCI on port %d", self._port)

    def stop(self) -> None:
        """Close TraCI connection and terminate SUMO."""
        if self._connected:
            try:
                traci.close()
            except Exception:
                pass
            self._connected = False
        if self._sumo_proc is not None:
            try:
                self._sumo_proc.terminate()
            except Exception:
                pass
            self._sumo_proc = None
        logger.info("[sumo_runner] SUMO stopped")

    def __enter__(self) -> "SumoRunner":
        self.connect()
        return self

    def __exit__(self, *args) -> None:
        self.stop()

    # ------------------------------------------------------------------
    # Simulation stepping
    # ------------------------------------------------------------------

    def step(self) -> float:
        """Advance simulation by one step_length_s. Returns current sim time."""
        traci.simulationStep()
        self._sim_time += self._step_length_s
        return self._sim_time

    @property
    def sim_time(self) -> float:
        """Current simulation time in seconds."""
        return self._sim_time

    # ------------------------------------------------------------------
    # Vehicle queries
    # ------------------------------------------------------------------

    def get_vehicle_ids(self) -> List[str]:
        """Return list of all vehicle IDs currently in the simulation."""
        return list(traci.vehicle.getIDList())

    def get_vehicle_position(self, vehicle_id: str) -> Optional[Tuple[float, float]]:
        """Return (x, y) position of a vehicle, or None if not found."""
        if vehicle_id not in traci.vehicle.getIDList():
            return None
        return traci.vehicle.getPosition(vehicle_id)

    def get_vehicle_speed(self, vehicle_id: str) -> float:
        """Return speed of vehicle in m/s, or 0.0 if not found."""
        if vehicle_id not in traci.vehicle.getIDList():
            return 0.0
        return traci.vehicle.getSpeed(vehicle_id)

    def get_vehicle_road(self, vehicle_id: str) -> str:
        """Return the road (edge) ID the vehicle is currently on."""
        return traci.vehicle.getRoadID(vehicle_id)

    def add_vehicle(
        self,
        vehicle_id: str,
        route_id: str,
        vehicle_type: str = "ambulance",
        depart_time: float = 0.0,
    ) -> None:
        """Insert a vehicle into the simulation.

        Args:
            vehicle_id:   Unique vehicle identifier.
            route_id:     One of the named routes in grid.rou.xml.
            vehicle_type: Vehicle type (e.g. "ambulance" or "car").
            depart_time:  Simulation time at which the vehicle departs.
        """
        traci.vehicle.add(
            vehID=vehicle_id,
            routeID=route_id,
            typeID=vehicle_type,
            depart=str(depart_time),
            departLane="best",
            departSpeed="max",
        )
        logger.info(
            "[sumo_runner] Added vehicle %s (type=%s route=%s depart=%.0f)",
            vehicle_id, vehicle_type, route_id, depart_time,
        )

    def remove_vehicle(self, vehicle_id: str) -> None:
        """Remove a vehicle from the simulation."""
        if vehicle_id in traci.vehicle.getIDList():
            traci.vehicle.remove(vehicle_id)

    # ------------------------------------------------------------------
    # Signal control
    # ------------------------------------------------------------------

    def get_phase(self, junction_id: str) -> int:
        """Return the current phase index at a junction."""
        return traci.trafficlight.getPhase(junction_id)

    def set_phase(self, junction_id: str, phase_index: int) -> None:
        """Override the signal phase at a junction.

        SAFETY: This is always called after JunctionSignalController validates
                the transition. Never call directly without safety check.
        """
        traci.trafficlight.setPhase(junction_id, phase_index)
        logger.info(
            "[sumo_runner] Set phase %d at junction %s", phase_index, junction_id
        )

    def set_phase_duration(self, junction_id: str, duration_s: float) -> None:
        """Set the remaining duration of the current phase."""
        traci.trafficlight.setPhaseDuration(junction_id, duration_s)

    def get_program(self, junction_id: str) -> str:
        """Return the current signal program ID at a junction."""
        return traci.trafficlight.getProgram(junction_id)

    def set_program(self, junction_id: str, program_id: str) -> None:
        """Switch to a different signal program at a junction."""
        traci.trafficlight.setProgram(junction_id, program_id)

    # ------------------------------------------------------------------
    # Detector queries
    # ------------------------------------------------------------------

    def get_detector_vehicle_count(self, detector_id: str) -> int:
        """Return the current vehicle count on an E2 detector."""
        return traci.lanearea.getLastStepVehicleNumber(detector_id)

    def get_detector_jam_length(self, detector_id: str) -> float:
        """Return the jam length (m) on an E2 detector."""
        return traci.lanearea.getJamLengthMetric(detector_id)

    def get_queue_length(self, junction_id: str, approach: str) -> int:
        """Return estimated queue length on an approach to a junction.

        Uses the corresponding E2 detector naming convention:
            det_{junction_id}_{approach}

        Returns 0 if the detector is not found.
        """
        det_id = f"det_{junction_id}_{approach}"
        try:
            return self.get_detector_vehicle_count(det_id)
        except Exception:
            return 0

    # ------------------------------------------------------------------
    # Simulation state
    # ------------------------------------------------------------------

    def get_min_expected_number(self) -> int:
        """Return number of vehicles expected to still depart."""
        return traci.simulation.getMinExpectedNumber()
