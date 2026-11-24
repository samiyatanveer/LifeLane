"""
metrics.py — Experiment metrics data structure for LifeLane Phase 6.
"""
from __future__ import annotations

from typing import NamedTuple


class ExperimentMetrics(NamedTuple):
    """Results of one simulation experiment run.

    Fields:
        scenario_id:              Unique identifier for this run.
        strategy:                 Corridor coordination strategy used.
        demand_level:             Traffic demand level ("light"/"medium"/"heavy").
        seed:                     Random seed used.
        ambulance_travel_time_s:  End-to-end travel time for the ambulance (s).
        average_queue_length:     Mean queue length across all junctions.
        safety_violations:        Count of detected safety violations.
        simulation_duration_s:    Total simulated time elapsed.
    """
    scenario_id: str
    strategy: str
    demand_level: str
    seed: int
    ambulance_travel_time_s: float
    average_queue_length: float
    safety_violations: int
    simulation_duration_s: float
