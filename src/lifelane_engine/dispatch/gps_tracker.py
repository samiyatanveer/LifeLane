"""
gps_tracker.py — GPS update tracking and staleness / deviation detection.

Receives periodic GpsUpdate events from an ambulance and maintains a
rolling history. Detects stale GPS (no recent update) and route deviation
(ambulance drifted too far from the planned corridor).

All coordinate arithmetic uses a flat-earth approximation suitable for the
short distances in the mock 2×2 grid simulation. Haversine is not needed
for a 1–2 km grid.

SAFETY RULE: Stale GPS is treated as a degraded state; the dispatch service
             must notify the operator and may fall back to the most recent
             known position (clearly flagged as stale).
"""
from __future__ import annotations

import logging
import math
import time
from collections import deque
from dataclasses import dataclass
from enum import Enum, auto
from typing import Deque, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Approximate metres per degree latitude/longitude at ~33° N (Pakistan/India region)
_M_PER_DEG_LAT: float = 111_320.0
_M_PER_DEG_LON: float = 93_270.0   # at 33° N: cos(33°) * 111_320

# Mock node positions for J1–J4 and H1 (lat, lon)
NODE_POSITIONS: Dict[str, Tuple[float, float]] = {
    "J1": (33.720, 73.040),
    "J2": (33.720, 73.045),
    "J3": (33.715, 73.040),
    "J4": (33.715, 73.045),
    "H1": (33.715, 73.047),
}


class GpsSource(Enum):
    """Origin of a GPS update."""
    DEVICE = auto()      # Onboard LifeLane device
    MANUAL = auto()      # GPS_MANUAL: operator-entered approximate location (2A)
    SIMULATED = auto()   # SUMO TraCI-derived position (Phase 3)


@dataclass
class GpsUpdate:
    """A single GPS position report from an ambulance."""
    ambulance_id: str
    latitude: float
    longitude: float
    speed_ms: float          # Speed in metres per second (≥ 0)
    heading_deg: float       # Compass heading in degrees [0, 360)
    timestamp: float         # Epoch seconds when measured
    source: GpsSource = GpsSource.DEVICE

    def __post_init__(self) -> None:
        if self.speed_ms < 0:
            raise ValueError(f"speed_ms must be >= 0, got {self.speed_ms}")
        if not (0.0 <= self.heading_deg < 360.0):
            raise ValueError(
                f"heading_deg must be in [0, 360), got {self.heading_deg}"
            )


class GpsTracker:
    """Tracks GPS updates for a single ambulance.

    Args:
        ambulance_id:           Ambulance this tracker belongs to.
        stale_threshold_s:      Seconds without an update before GPS is stale.
        max_history:            Rolling window size for GPS history.
        deviation_corridor_m:   Max metres from nearest route node before
                                deviation is flagged.
    """

    def __init__(
        self,
        ambulance_id: str,
        stale_threshold_s: float = 10.0,
        max_history: int = 50,
        deviation_corridor_m: float = 30.0,
    ) -> None:
        self.ambulance_id = ambulance_id
        self.stale_threshold_s = stale_threshold_s
        self.deviation_corridor_m = deviation_corridor_m
        self._history: Deque[GpsUpdate] = deque(maxlen=max_history)

    # ------------------------------------------------------------------
    # Update and query
    # ------------------------------------------------------------------

    def update(self, gps: GpsUpdate) -> None:
        """Record a new GPS fix."""
        if gps.ambulance_id != self.ambulance_id:
            raise ValueError(
                f"GPS update for ambulance {gps.ambulance_id!r} "
                f"delivered to tracker for {self.ambulance_id!r}"
            )
        self._history.append(gps)
        logger.debug(
            "[gps] %s lat=%.6f lon=%.6f speed=%.1f m/s src=%s",
            self.ambulance_id, gps.latitude, gps.longitude,
            gps.speed_ms, gps.source.name,
        )

    def latest(self) -> Optional[GpsUpdate]:
        """Return the most recent GPS update, or None if no updates received."""
        if not self._history:
            return None
        return self._history[-1]

    def history(self) -> List[GpsUpdate]:
        """Return a copy of the GPS history list (oldest first)."""
        return list(self._history)

    def clear(self) -> None:
        """Clear all stored GPS data (e.g. after a request completes)."""
        self._history.clear()

    # ------------------------------------------------------------------
    # Staleness
    # ------------------------------------------------------------------

    def is_stale(self, now: Optional[float] = None) -> bool:
        """Return True if no GPS update has arrived within stale_threshold_s.

        Also returns True if no updates have ever been received.
        """
        if now is None:
            now = time.time()
        last = self.latest()
        if last is None:
            return True
        return (now - last.timestamp) > self.stale_threshold_s

    # ------------------------------------------------------------------
    # Route deviation
    # ------------------------------------------------------------------

    def check_deviation(
        self,
        planned_node_positions: Optional[Dict[str, Tuple[float, float]]] = None,
    ) -> bool:
        """Return True if the ambulance has deviated from the planned corridor.

        Uses Euclidean distance on a flat-earth approximation to find the
        nearest planned node. If the distance exceeds deviation_corridor_m,
        the ambulance is considered off-route.

        Args:
            planned_node_positions: Dict of node_id → (lat, lon). Defaults to
                                    NODE_POSITIONS (mock grid).

        Returns:
            True if off-route deviation detected; False if on-route or no GPS.
        """
        last = self.latest()
        if last is None:
            return False  # No data → cannot detect deviation

        if planned_node_positions is None:
            planned_node_positions = NODE_POSITIONS

        min_dist_m = float("inf")
        for node_id, (nlat, nlon) in planned_node_positions.items():
            dlat = (last.latitude - nlat) * _M_PER_DEG_LAT
            dlon = (last.longitude - nlon) * _M_PER_DEG_LON
            dist = math.sqrt(dlat ** 2 + dlon ** 2)
            if dist < min_dist_m:
                min_dist_m = dist

        deviated = min_dist_m > self.deviation_corridor_m
        if deviated:
            logger.warning(
                "[gps] %s deviation detected: %.1f m from nearest route node "
                "(threshold %.1f m)",
                self.ambulance_id, min_dist_m, self.deviation_corridor_m,
            )
        return deviated

