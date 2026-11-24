"""
scenario.py — Scenario configuration and runner for LifeLane simulations.

Defines ScenarioConfig and the ScenarioRunner that orchestrates:
  - Ambulance dispatch (via DispatchService)
  - Signal control (via JunctionSignalController)
  - Simulation stepping (via SumoRunner or MockSumoRunner)
  - GPS updates (from TraCI vehicle positions -> GpsTracker)
  - Metrics collection (ExperimentMetrics)

Phase 3 requires SUMO; MockSumoRunner is used when SUMO is unavailable.

*** SIMULATION ONLY — never connected to real traffic infrastructure ***
"""
from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from lifelane_engine.dispatch.gps_tracker import GpsSource, GpsUpdate
from lifelane_engine.simulation.metrics import ExperimentMetrics

logger = logging.getLogger(__name__)

# Approximate GPS conversion for mock grid (flat-earth)
# Grid origin J3 = (0,0) in metres; J1 = (0, 300)
_LAT_ORIGIN = 33.720
_LON_ORIGIN = 73.040
_M_PER_DEG_LAT = 111_320.0
_M_PER_DEG_LON = 93_270.0  # at 33 degrees N


def xy_to_latlon(x: float, y: float) -> Tuple[float, float]:
    """Convert mock grid XY (metres) to approximate lat/lon."""
    lat = _LAT_ORIGIN + y / _M_PER_DEG_LAT
    lon = _LON_ORIGIN + x / _M_PER_DEG_LON
    return lat, lon


@dataclass
class ScenarioConfig:
    """Configuration for one simulation scenario run.

    Fields:
        scenario_id:       Unique identifier.
        demand_level:      Traffic demand ("light", "medium", "heavy").
        seed:              Random seed for SUMO and synthetic data.
        ambulance_route:   "r_amb_A" or "r_amb_B".
        ambulance_depart:  Simulation time at which ambulance departs.
        use_coordination:  Whether to apply signal preemption.
        strategy:          Corridor strategy ("baseline", "fixed_formula",
                           "naive_eta", "learned_eta").
        duration_s:        Total simulation duration in seconds.
        step_length_s:     TraCI step size.
    """
    scenario_id: str = "default"
    demand_level: str = "light"         # "light" | "medium" | "heavy"
    seed: int = 42
    ambulance_route: str = "r_amb_A"    # Route A (J1->J2->J4->H1) or B (J1->J3->J4->H1)
    ambulance_depart: float = 60.0      # seconds into simulation
    use_coordination: bool = True
    strategy: str = "naive_eta"
    duration_s: float = 600.0
    step_length_s: float = 1.0

    # Demand multipliers per level
    _DEMAND_MULTIPLIERS: Dict[str, float] = field(
        default_factory=lambda: {"light": 0.3, "medium": 0.6, "heavy": 1.0}
    )

    @property
    def demand_multiplier(self) -> float:
        """Return the numeric demand multiplier for this scenario's level."""
        return self._DEMAND_MULTIPLIERS.get(self.demand_level, 0.3)


class ScenarioRunner:
    """Orchestrates a single simulation scenario.

    Works with either SumoRunner or MockSumoRunner; the caller passes
    the runner as a dependency so tests can inject the mock.

    Args:
        config:           Scenario parameters.
        runner:           SumoRunner or MockSumoRunner instance (already connected).
        dispatch_service: Wired DispatchService (from build_default_dispatch_service).
        signal_controllers: Dict of junction_id -> JunctionSignalController.
    """

    AMBULANCE_VID = "ambulance_001"

    def __init__(
        self,
        config: ScenarioConfig,
        runner,   # SumoRunner | MockSumoRunner
        dispatch_service=None,
        signal_controllers: Optional[Dict] = None,
    ) -> None:
        self._config = config
        self._runner = runner
        self._dispatch = dispatch_service
        self._controllers: Dict = signal_controllers or {}

        # Metrics accumulators
        self._ambulance_travel_times: List[float] = []
        self._queue_lengths_at_junctions: Dict[str, List[int]] = {
            "J1": [], "J2": [], "J3": [], "J4": []
        }
        self._safety_violations: int = 0
        self._ambulance_depart_time: Optional[float] = None
        self._ambulance_arrive_time: Optional[float] = None

    def run(self) -> ExperimentMetrics:
        """Step through the simulation and collect metrics.

        Returns:
            ExperimentMetrics with collected results.
        """
        logger.info(
            "[scenario] Starting scenario %s (demand=%s seed=%d strategy=%s)",
            self._config.scenario_id,
            self._config.demand_level,
            self._config.seed,
            self._config.strategy,
        )

        # Insert ambulance into simulation
        self._runner.add_vehicle(
            vehicle_id=self.AMBULANCE_VID,
            route_id=self._config.ambulance_route,
            vehicle_type="ambulance",
            depart_time=self._config.ambulance_depart,
        )
        self._ambulance_depart_time = self._config.ambulance_depart

        # Track whether ambulance has departed yet
        ambulance_departed = False

        sim_step = 0
        max_steps = int(self._config.duration_s / self._config.step_length_s)

        while sim_step < max_steps:
            t = self._runner.step()
            sim_step += 1

            # Collect queue lengths every step
            for junc in self._queue_lengths_at_junctions:
                ql = self._runner.get_queue_length(junc, "north")
                self._queue_lengths_at_junctions[junc].append(ql)

            # Check ambulance departure
            if not ambulance_departed and t >= self._config.ambulance_depart:
                pos = self._runner.get_vehicle_position(self.AMBULANCE_VID)
                if pos is not None:
                    ambulance_departed = True
                    logger.debug("[scenario] Ambulance departed at t=%.1f", t)

            # Track GPS and arrival
            if ambulance_departed and self._ambulance_arrive_time is None:
                self._track_ambulance(t)

                # Check for arrival via mock_sumo has_arrived or vehicle disappearing
                arrived = False
                if hasattr(self._runner, "vehicle_has_arrived"):
                    arrived = self._runner.vehicle_has_arrived(self.AMBULANCE_VID)
                else:
                    # Real SUMO: vehicle leaves the vehicle list when arrived
                    arrived = self.AMBULANCE_VID not in self._runner.get_vehicle_ids()

                if arrived:
                    self._ambulance_arrive_time = t
                    logger.info(
                        "[scenario] Ambulance arrived at t=%.1f (travel=%.1fs)",
                        t, t - self._ambulance_depart_time,
                    )
                    break

        # If ambulance still hasn't arrived but simulation ended, record final time
        if ambulance_departed and self._ambulance_arrive_time is None:
            self._ambulance_arrive_time = self._runner.sim_time
            logger.warning(
                "[scenario] Scenario ended before arrival confirmed; using sim end time"
            )

        metrics = self._build_metrics()
        logger.info(
            "[scenario] Scenario %s complete: amb_travel=%.1fs violations=%d",
            self._config.scenario_id,
            metrics.ambulance_travel_time_s,
            metrics.safety_violations,
        )
        return metrics

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _track_ambulance(self, t: float) -> None:
        """Update ambulance GPS via dispatch service."""
        pos = self._runner.get_vehicle_position(self.AMBULANCE_VID)
        if pos is None:
            return

        speed = self._runner.get_vehicle_speed(self.AMBULANCE_VID)
        lat, lon = xy_to_latlon(pos[0], pos[1])

        # Feed GPS into dispatch service if wired
        if self._dispatch is not None:
            gps = GpsUpdate(
                ambulance_id="LL-001",
                latitude=lat,
                longitude=lon,
                speed_ms=speed,
                heading_deg=90.0,
                timestamp=t,
                source=GpsSource.SIMULATED,
            )
            self._dispatch.process_gps_update("LL-001", gps, now=t)

    def _build_metrics(self) -> ExperimentMetrics:
        """Assemble an ExperimentMetrics NamedTuple from collected data."""
        travel_time = (
            (self._ambulance_arrive_time - self._ambulance_depart_time)
            if self._ambulance_arrive_time is not None
            and self._ambulance_depart_time is not None
            else float("nan")
        )

        avg_queue = {
            junc: (sum(ql) / len(ql) if ql else 0.0)
            for junc, ql in self._queue_lengths_at_junctions.items()
        }
        avg_queue_all = (
            sum(avg_queue.values()) / len(avg_queue) if avg_queue else 0.0
        )

        return ExperimentMetrics(
            scenario_id=self._config.scenario_id,
            strategy=self._config.strategy,
            demand_level=self._config.demand_level,
            seed=self._config.seed,
            ambulance_travel_time_s=travel_time,
            average_queue_length=avg_queue_all,
            safety_violations=self._safety_violations,
            simulation_duration_s=self._runner.sim_time,
        )
