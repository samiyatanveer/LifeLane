"""
mock_sumo.py — Mock TraCI / SUMO simulation for SUMO-free testing.

Simulates vehicle movement through the 2x2 mock grid without requiring
SUMO or TraCI to be installed. Used in Phase 3 tests and Phase 5 synthetic
dataset generation.

All vehicle positions are computed using a simple kinematic model:
    position += speed * dt

Junction detection uses proximity thresholds on the mock grid coordinates.

*** MOCK DATA ONLY — never connected to real traffic infrastructure ***
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Mock grid geometry (metres from origin)
# ─────────────────────────────────────────────────────────────────────────────

NODE_XY: Dict[str, Tuple[float, float]] = {
    "J1": (0.0,   300.0),
    "J2": (300.0, 300.0),
    "J3": (0.0,   0.0),
    "J4": (300.0, 0.0),
    "H1": (350.0, 0.0),
}

# Ordered route definitions (node sequences)
ROUTE_NODES: Dict[str, List[str]] = {
    "r_amb_A": ["J1", "J2", "J4", "H1"],
    "r_amb_B": ["J1", "J3", "J4", "H1"],
    "r_EW_J1J2": ["J1", "J2"],
    "r_WE_J2J1": ["J2", "J1"],
    "r_NS_J1J3": ["J1", "J3"],
    "r_SN_J3J1": ["J3", "J1"],
    "r_J2J4":   ["J2", "J4"],
    "r_J4J2":   ["J4", "J2"],
    "r_J3J4":   ["J3", "J4"],
    "r_J4J3":   ["J4", "J3"],
}

# Proximity threshold for "arrived at node" detection (metres)
_ARRIVAL_THRESHOLD_M = 15.0


@dataclass
class MockVehicle:
    """State of a single simulated vehicle."""
    vehicle_id: str
    route_id: str
    vehicle_type: str = "car"
    speed_ms: float = 10.0
    # Current position along the route as fraction [0, 1]
    route_progress: float = 0.0
    depart_time: float = 0.0
    arrived: bool = False
    current_node_index: int = 0  # Index into ROUTE_NODES[route_id]

    def position_xy(self) -> Tuple[float, float]:
        """Interpolate current XY position along the route."""
        nodes = ROUTE_NODES.get(self.route_id, [])
        if len(nodes) < 2:
            return (0.0, 0.0)
        # Map route_progress to segment
        n_segs = len(nodes) - 1
        seg_frac = self.route_progress * n_segs
        seg_idx = min(int(seg_frac), n_segs - 1)
        local_frac = seg_frac - seg_idx
        x0, y0 = NODE_XY[nodes[seg_idx]]
        x1, y1 = NODE_XY[nodes[seg_idx + 1]]
        x = x0 + (x1 - x0) * local_frac
        y = y0 + (y1 - y0) * local_frac
        return (x, y)

    def current_road(self) -> str:
        """Return a synthetic edge ID for the current segment."""
        nodes = ROUTE_NODES.get(self.route_id, [])
        if not nodes or len(nodes) < 2:
            return "unknown"
        n_segs = len(nodes) - 1
        seg_idx = min(int(self.route_progress * n_segs), n_segs - 1)
        return f"e_{nodes[seg_idx]}_{nodes[seg_idx + 1]}"


class MockSumoRunner:
    """Pure-Python SUMO/TraCI replacement for testing without SUMO installed.

    Simulates vehicle kinetics, junction arrivals, signal phases, and
    detector counts on the mock 2x2 grid.

    Args:
        step_length_s: Simulation step duration in seconds.
        seed:          Random seed (not used internally; accepted for API compat).
    """

    def __init__(self, step_length_s: float = 1.0, seed: int = 42) -> None:
        self._step_length_s = step_length_s
        self._sim_time: float = 0.0
        self._vehicles: Dict[str, MockVehicle] = {}
        # Signal phases per junction: simple cycle counter
        self._signal_phases: Dict[str, int] = {j: 0 for j in NODE_XY}
        self._signal_timers: Dict[str, float] = {j: 0.0 for j in NODE_XY}
        self._phase_durations = [27, 3, 3, 24, 3]  # seconds, matches grid.tll.xml
        self._n_phases = len(self._phase_durations)

    # ------------------------------------------------------------------
    # Connection lifecycle (no-ops for mock)
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """No-op: mock runner needs no connection."""
        logger.info("[mock_sumo] MockSumoRunner connected (no SUMO required)")

    def stop(self) -> None:
        """No-op: mock runner has nothing to shut down."""
        logger.info("[mock_sumo] MockSumoRunner stopped")

    def __enter__(self) -> "MockSumoRunner":
        self.connect()
        return self

    def __exit__(self, *args) -> None:
        self.stop()

    # ------------------------------------------------------------------
    # Simulation stepping
    # ------------------------------------------------------------------

    def step(self) -> float:
        """Advance all vehicles and signals by one step. Returns sim time."""
        dt = self._step_length_s
        self._sim_time += dt

        # Advance signal timers
        for junc in list(NODE_XY.keys()):
            self._signal_timers[junc] += dt
            current_phase = self._signal_phases[junc]
            if self._signal_timers[junc] >= self._phase_durations[current_phase]:
                self._signal_timers[junc] = 0.0
                self._signal_phases[junc] = (current_phase + 1) % self._n_phases

        # Move vehicles
        for vid, veh in list(self._vehicles.items()):
            if veh.arrived or self._sim_time < veh.depart_time:
                continue
            nodes = ROUTE_NODES.get(veh.route_id, [])
            if not nodes:
                continue
            # Total route length
            total_len = self._route_length(veh.route_id)
            if total_len <= 0:
                veh.arrived = True
                continue
            dist_per_step = veh.speed_ms * dt
            progress_inc = dist_per_step / total_len
            veh.route_progress = min(1.0, veh.route_progress + progress_inc)
            if veh.route_progress >= 1.0:
                veh.arrived = True
                logger.debug("[mock_sumo] Vehicle %s arrived at destination", vid)

        return self._sim_time

    @property
    def sim_time(self) -> float:
        """Current simulation time in seconds."""
        return self._sim_time

    # ------------------------------------------------------------------
    # Vehicle management
    # ------------------------------------------------------------------

    def add_vehicle(
        self,
        vehicle_id: str,
        route_id: str,
        vehicle_type: str = "ambulance",
        depart_time: float = 0.0,
        speed_ms: float = 13.89,
    ) -> None:
        """Insert a vehicle into the mock simulation."""
        if route_id not in ROUTE_NODES:
            logger.warning(
                "[mock_sumo] Unknown route_id %s for vehicle %s", route_id, vehicle_id
            )
        self._vehicles[vehicle_id] = MockVehicle(
            vehicle_id=vehicle_id,
            route_id=route_id,
            vehicle_type=vehicle_type,
            speed_ms=speed_ms,
            depart_time=depart_time,
        )
        logger.info(
            "[mock_sumo] Added vehicle %s (type=%s route=%s depart=%.0f)",
            vehicle_id, vehicle_type, route_id, depart_time,
        )

    def remove_vehicle(self, vehicle_id: str) -> None:
        """Remove a vehicle from the simulation."""
        self._vehicles.pop(vehicle_id, None)

    def get_vehicle_ids(self) -> List[str]:
        """Return IDs of all non-arrived vehicles currently in the simulation."""
        return [
            vid for vid, v in self._vehicles.items()
            if not v.arrived and self._sim_time >= v.depart_time
        ]

    def get_vehicle_position(self, vehicle_id: str) -> Optional[Tuple[float, float]]:
        """Return (x, y) position or None if not found / not yet departed."""
        veh = self._vehicles.get(vehicle_id)
        if veh is None or self._sim_time < veh.depart_time or veh.arrived:
            return None
        return veh.position_xy()

    def get_vehicle_speed(self, vehicle_id: str) -> float:
        """Return vehicle speed in m/s."""
        veh = self._vehicles.get(vehicle_id)
        if veh is None:
            return 0.0
        return veh.speed_ms

    def get_vehicle_road(self, vehicle_id: str) -> str:
        """Return synthetic edge ID for current vehicle segment."""
        veh = self._vehicles.get(vehicle_id)
        if veh is None:
            return ""
        return veh.current_road()

    def vehicle_has_arrived(self, vehicle_id: str) -> bool:
        """Return True if the vehicle has completed its route."""
        veh = self._vehicles.get(vehicle_id)
        return veh.arrived if veh else True

    def get_vehicle_nearest_junction(self, vehicle_id: str) -> Optional[str]:
        """Return the nearest junction node to the vehicle's current position."""
        pos = self.get_vehicle_position(vehicle_id)
        if pos is None:
            return None
        x, y = pos
        best_node = None
        best_dist = float("inf")
        for node_id, (nx, ny) in NODE_XY.items():
            dist = math.sqrt((x - nx) ** 2 + (y - ny) ** 2)
            if dist < best_dist:
                best_dist = dist
                best_node = node_id
        return best_node

    def is_vehicle_at_junction(
        self, vehicle_id: str, junction_id: str
    ) -> bool:
        """Return True if vehicle is within arrival threshold of junction."""
        pos = self.get_vehicle_position(vehicle_id)
        if pos is None:
            return False
        if junction_id not in NODE_XY:
            return False
        x, y = pos
        nx, ny = NODE_XY[junction_id]
        dist = math.sqrt((x - nx) ** 2 + (y - ny) ** 2)
        return dist <= _ARRIVAL_THRESHOLD_M

    # ------------------------------------------------------------------
    # Signal control
    # ------------------------------------------------------------------

    def get_phase(self, junction_id: str) -> int:
        """Return current phase index at a junction."""
        return self._signal_phases.get(junction_id, 0)

    def set_phase(self, junction_id: str, phase_index: int) -> None:
        """Override the signal phase (called after safety controller approval)."""
        if junction_id not in self._signal_phases:
            logger.warning("[mock_sumo] Unknown junction %s for set_phase", junction_id)
            return
        self._signal_phases[junction_id] = phase_index % self._n_phases
        self._signal_timers[junction_id] = 0.0
        logger.info(
            "[mock_sumo] Phase set to %d at junction %s", phase_index, junction_id
        )

    def set_phase_duration(self, junction_id: str, duration_s: float) -> None:
        """No-op in mock (duration is implicit from phase_durations list)."""
        pass

    def get_program(self, junction_id: str) -> str:
        """Return mock program ID."""
        return "lifelane_fixed"

    def set_program(self, junction_id: str, program_id: str) -> None:
        """No-op in mock."""
        pass

    # ------------------------------------------------------------------
    # Detector queries
    # ------------------------------------------------------------------

    def get_detector_vehicle_count(self, detector_id: str) -> int:
        """Return approximate vehicle count near the detector's junction/approach."""
        # Parse detector naming: det_{junction}_{approach}
        parts = detector_id.split("_")
        if len(parts) < 2:
            return 0
        junction_id = parts[1] if len(parts) >= 2 else ""
        count = 0
        for veh in self._vehicles.values():
            if veh.arrived or self._sim_time < veh.depart_time:
                continue
            nearest = self.get_vehicle_nearest_junction(veh.vehicle_id)
            if nearest == junction_id:
                count += 1
        return count

    def get_queue_length(self, junction_id: str, approach: str) -> int:
        """Return estimated queue length at a junction approach."""
        det_id = f"det_{junction_id}_{approach}"
        return self.get_detector_vehicle_count(det_id)

    def get_min_expected_number(self) -> int:
        """Return count of non-arrived vehicles."""
        return sum(1 for v in self._vehicles.values() if not v.arrived)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _route_length(route_id: str) -> float:
        """Return total Euclidean length of a route in metres."""
        nodes = ROUTE_NODES.get(route_id, [])
        if len(nodes) < 2:
            return 0.0
        total = 0.0
        for i in range(len(nodes) - 1):
            x0, y0 = NODE_XY[nodes[i]]
            x1, y1 = NODE_XY[nodes[i + 1]]
            total += math.sqrt((x1 - x0) ** 2 + (y1 - y0) ** 2)
        return total

