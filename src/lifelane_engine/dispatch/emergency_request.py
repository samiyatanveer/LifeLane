"""
emergency_request.py — Enriched emergency request wrapping AmbulanceRequest.

EmergencyRequest composes an AmbulanceRequest and adds Phase 2 dispatch
metadata: verification tier, GPS source, per-junction ETAs, and
dynamic reroute count.

Junction ETA calculation uses a naive distance/speed formula; Phase 5
will replace this with the trained XGBoost model.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from lifelane_engine.ambulance.request import AmbulanceRequest, RequestStatus
from lifelane_engine.dispatch.verification_state import (
    VerificationConfidence,
    VerificationLevel,
    VerificationMethod,
)

logger = logging.getLogger(__name__)

# Approximate metres per degree (flat-earth for mock grid)
_M_PER_DEG_LAT: float = 111_320.0
_M_PER_DEG_LON: float = 93_270.0


def compute_naive_etas(
    route_junctions: List[str],
    distances_m: Dict[Tuple[str, str], float],
    speed_ms: float,
    base_time: float = 0.0,
) -> Dict[str, float]:
    """Compute naive per-junction ETAs using constant speed.

    Args:
        route_junctions: Ordered list of junction IDs on the route.
        distances_m:     Dict of (from_node, to_node) → distance in metres.
        speed_ms:        Current ambulance speed in m/s (minimum 1.0 m/s applied).
        base_time:       Epoch time at which the ambulance is at the first junction.

    Returns:
        Dict mapping junction_id → predicted arrival epoch time.
    """
    if speed_ms < 1.0:
        speed_ms = 1.0  # Avoid division by zero or unreasonably slow

    etas: Dict[str, float] = {}
    cumulative_s = base_time

    for i, junc in enumerate(route_junctions):
        if i == 0:
            etas[junc] = cumulative_s
            continue
        prev = route_junctions[i - 1]
        dist = distances_m.get((prev, junc), distances_m.get((junc, prev), 300.0))
        cumulative_s += dist / speed_ms
        etas[junc] = cumulative_s

    return etas


@dataclass
class EmergencyRequest:
    """An enriched emergency request carrying full dispatch context.

    Wraps an AmbulanceRequest via composition and adds:
    - Verification tier metadata
    - GPS source
    - Per-junction ETAs (naive in Phase 2; ML-based from Phase 5)
    - Dynamic reroute count
    - A log of notifications sent
    """
    base_request: AmbulanceRequest
    is_registered: bool
    verification_level: VerificationLevel
    verification_method: VerificationMethod
    verification_confidence: VerificationConfidence
    gps_source: str = "DEVICE"             # "DEVICE" | "MANUAL" | "SIMULATED"
    junction_etas: Dict[str, float] = field(default_factory=dict)
    dynamic_reroute_count: int = 0
    notification_log: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    # ------------------------------------------------------------------
    # Delegation helpers (forward key attributes to base_request)
    # ------------------------------------------------------------------

    @property
    def request_id(self) -> str:
        """Unique ID of the underlying AmbulanceRequest."""
        return self.base_request.request_id

    @property
    def ambulance_id(self) -> str:
        """LifeLane or temp ambulance identifier."""
        return self.base_request.ambulance_id

    @property
    def hospital_id(self) -> str:
        """Selected hospital destination."""
        return self.base_request.hospital_id

    @property
    def approach(self) -> str:
        """Approach direction at the requesting junction."""
        return self.base_request.approach

    @property
    def junction_id(self) -> str:
        """Junction where priority is requested."""
        return self.base_request.junction_id

    @property
    def route(self) -> List[str]:
        """Ordered route edges."""
        return self.base_request.route

    @property
    def status(self) -> RequestStatus:
        """Current lifecycle status of the base request."""
        return self.base_request.status

    @property
    def is_authorized(self) -> bool:
        """Return True if this request has AUTHORIZED verification level."""
        return self.verification_level == VerificationLevel.AUTHORIZED

    # ------------------------------------------------------------------
    # ETA update
    # ------------------------------------------------------------------

    def update_junction_etas(
        self,
        current_speed_ms: float,
        route_junctions: List[str],
        distances_m: Optional[Dict[Tuple[str, str], float]] = None,
        now: Optional[float] = None,
    ) -> None:
        """Recalculate per-junction ETAs using current speed.

        In Phase 5 this will delegate to the XGBoost ETA model.

        Args:
            current_speed_ms: Ambulance speed from latest GPS update.
            route_junctions:  Ordered list of remaining junction IDs.
            distances_m:      Optional distance map; uses default mock distances
                              if not provided.
            now:              Override current epoch time.
        """
        if now is None:
            now = time.time()

        if distances_m is None:
            # Default mock inter-junction distances (metres)
            distances_m = {
                ("J1", "J2"): 300.0,
                ("J1", "J3"): 350.0,
                ("J2", "J4"): 300.0,
                ("J3", "J4"): 350.0,
                ("J4", "H1"): 50.0,
            }

        self.junction_etas = compute_naive_etas(
            route_junctions=route_junctions,
            distances_m=distances_m,
            speed_ms=current_speed_ms,
            base_time=now,
        )
        logger.debug(
            "[emergency_req] Updated ETAs for %s: %s",
            self.ambulance_id, self.junction_etas,
        )

    def log_notification(self, event_type: str, message: str) -> None:
        """Append a notification event to the local log."""
        entry = f"{event_type}: {message}"
        self.notification_log.append(entry)

    def __repr__(self) -> str:
        return (
            f"EmergencyRequest(id={self.request_id!r}, "
            f"amb={self.ambulance_id!r}, "
            f"verified={self.verification_level.name}, "
            f"status={self.status.name})"
        )

