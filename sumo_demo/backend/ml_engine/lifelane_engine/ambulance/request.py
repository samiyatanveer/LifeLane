"""
request.py — Ambulance request data model and validation.

SAFETY RULE: A siren classifier does NOT prove ambulance identity.
             Requests must be validated, authorized, and unexpired
             BEFORE any signal-priority action is taken.
"""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional

logger = logging.getLogger(__name__)

VALID_APPROACHES = frozenset(("north", "east", "south", "west"))
VALID_EMERGENCY_MODES = frozenset(("lights_and_sirens", "lights_only", "none"))


class RequestStatus(Enum):
    """Lifecycle status of an ambulance priority request."""
    PENDING = auto()
    AUTHORIZED = auto()
    ACTIVE = auto()
    COMPLETED = auto()
    REJECTED = auto()
    EXPIRED = auto()
    CANCELLED = auto()


@dataclass
class AmbulanceRequest:
    """A simulated, authorized ambulance signal-priority request.

    All fields are validated on construction. Validation errors raise
    ValueError with a descriptive message.

    Fields:
        ambulance_id:        Unique ambulance identifier.
        origin_edge:         SUMO edge ID where the ambulance starts.
        destination_edge:    SUMO edge ID of the hospital destination.
        hospital_id:         Selected hospital from the mock directory.
        approach:            Approach direction at the requesting junction.
        junction_id:         Junction where priority is requested.
        route:               Ordered list of SUMO edge IDs forming the route.
        emergency_mode:      One of VALID_EMERGENCY_MODES.
        authorization_token: Simulated token proving dispatch authorization.
        request_id:          Auto-generated UUID.
        created_at:          Creation epoch timestamp.
        expiry_at:           Expiry epoch timestamp.
        status:              Lifecycle status.
    """

    ambulance_id: str
    origin_edge: str
    destination_edge: str
    hospital_id: str
    approach: str
    junction_id: str
    route: List[str]
    emergency_mode: str
    authorization_token: str
    expiry_s: float = 300.0  # seconds from creation

    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: float = field(default_factory=time.time)
    status: RequestStatus = field(default=RequestStatus.PENDING, init=False)

    # Set after creation
    expiry_at: float = field(init=False)

    def __post_init__(self) -> None:
        self.expiry_at = self.created_at + self.expiry_s
        self._validate()

    def _validate(self) -> None:
        """Validate all fields; raise ValueError on any failure."""
        errors: list[str] = []

        if not self.ambulance_id.strip():
            errors.append("ambulance_id must not be empty")
        if not self.origin_edge.strip():
            errors.append("origin_edge must not be empty")
        if not self.destination_edge.strip():
            errors.append("destination_edge must not be empty")
        if not self.hospital_id.strip():
            errors.append("hospital_id must not be empty")
        if self.approach not in VALID_APPROACHES:
            errors.append(f"approach '{self.approach}' must be one of {sorted(VALID_APPROACHES)}")
        if not self.junction_id.strip():
            errors.append("junction_id must not be empty")
        if not self.route:
            errors.append("route must contain at least one edge")
        if self.emergency_mode not in VALID_EMERGENCY_MODES:
            errors.append(
                f"emergency_mode '{self.emergency_mode}' must be one of {sorted(VALID_EMERGENCY_MODES)}"
            )
        if not self.authorization_token.strip():
            errors.append("authorization_token must not be empty")
        if self.expiry_s <= 0:
            errors.append("expiry_s must be positive")

        if errors:
            raise ValueError(
                f"AmbulanceRequest validation failed for ambulance '{self.ambulance_id}':\n"
                + "\n".join(f"  - {e}" for e in errors)
            )

        logger.debug(
            "[request] Created request %s for ambulance %s at junction %s approach %s",
            self.request_id, self.ambulance_id, self.junction_id, self.approach,
        )

    # ------------------------------------------------------------------
    # Status helpers
    # ------------------------------------------------------------------

    def is_expired(self, now: float | None = None) -> bool:
        """Return True if the request has passed its expiry timestamp."""
        if now is None:
            now = time.time()
        return now > self.expiry_at

    def is_valid(self, now: float | None = None) -> bool:
        """Return True if the request is authorized and not expired."""
        return (
            self.status == RequestStatus.AUTHORIZED
            and not self.is_expired(now=now)
        )

    def authorize(self, now: float | None = None) -> None:
        """Mark the request as simulated-authorized.

        In the real system, this would be an external dispatch-system check.
        For the POC, authorization is simulated via the token field.
        """
        if self.status != RequestStatus.PENDING:
            raise ValueError(
                f"Cannot authorize request {self.request_id}: current status is {self.status}"
            )
        if self.is_expired(now=now):
            self.status = RequestStatus.EXPIRED
            raise ValueError(
                f"Cannot authorize request {self.request_id}: already expired"
            )
        self.status = RequestStatus.AUTHORIZED
        logger.info(
            "[request] Authorized request %s for ambulance %s",
            self.request_id, self.ambulance_id,
        )

    def reject(self, reason: str = "") -> None:
        """Reject the request (e.g. failed validation)."""
        self.status = RequestStatus.REJECTED
        logger.warning(
            "[request] Rejected request %s: %s", self.request_id, reason
        )

    def expire(self) -> None:
        """Mark request as expired."""
        self.status = RequestStatus.EXPIRED
        logger.warning(
            "[request] Expired request %s for ambulance %s",
            self.request_id, self.ambulance_id,
        )

    def activate(self) -> None:
        """Mark request as actively being served."""
        self.status = RequestStatus.ACTIVE

    def complete(self) -> None:
        """Mark request as completed after passage confirmation."""
        self.status = RequestStatus.COMPLETED
        logger.info(
            "[request] Completed request %s — ambulance %s passed",
            self.request_id, self.ambulance_id,
        )

    def cancel(self, reason: str = "") -> None:
        """Cancel an active request (e.g. network fault, reroute)."""
        self.status = RequestStatus.CANCELLED
        logger.warning(
            "[request] Cancelled request %s: %s", self.request_id, reason
        )

    def __repr__(self) -> str:
        return (
            f"AmbulanceRequest(id={self.request_id!r}, amb={self.ambulance_id!r}, "
            f"junction={self.junction_id!r}, approach={self.approach!r}, "
            f"status={self.status.name})"
        )


# ---------------------------------------------------------------------------
# Mock factory — dataset-free POC helper
# ---------------------------------------------------------------------------

def make_mock_request(
    ambulance_id: str = "AMB-001",
    junction_id: str = "J1",
    approach: str = "north",
    hospital_id: str = "H1",
    origin_edge: str = "edge_n_J1",
    destination_edge: str = "edge_J4_hospital",
    route: Optional[List[str]] = None,
    authorization_token: str = "SIM-TOKEN-VALID",
    emergency_mode: str = "lights_and_sirens",
    expiry_s: float = 300.0,
    created_at: Optional[float] = None,
) -> AmbulanceRequest:
    """Create a mock ambulance request for dataset-free POC testing.

    Returns a PENDING request. Caller must call .authorize() to activate it.
    """
    if route is None:
        route = [origin_edge, "edge_J1_J2", "edge_J2_J4", destination_edge]
    if created_at is None:
        created_at = time.time()

    req = AmbulanceRequest(
        ambulance_id=ambulance_id,
        origin_edge=origin_edge,
        destination_edge=destination_edge,
        hospital_id=hospital_id,
        approach=approach,
        junction_id=junction_id,
        route=route,
        emergency_mode=emergency_mode,
        authorization_token=authorization_token,
        expiry_s=expiry_s,
        created_at=created_at,
    )
    return req

