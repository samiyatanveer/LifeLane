"""
temp_verification.py — Temporary verification pathway for unregistered ambulances.

Supports three verification methods (Decision 6A):
    DISPATCH_OPERATOR — operator presents a valid token (HIGH confidence)
    AMBULANCE_APP     — ambulance app sends full payload (MEDIUM confidence)
    LICENSE_PLATE     — plate looked up in mock dict (LOW confidence if found)

Decision 2A: GPS_MANUAL location is accepted for unregistered ambulances.

SAFETY RULE: Temporary verification does NOT grant signal priority.
             Only the safety controller can authorize priority after a
             request reaches VERIFIED state.
"""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional

from lifelane_engine.dispatch.verification_state import (
    VerificationConfidence,
    VerificationMethod,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Verification outcome
# ---------------------------------------------------------------------------

class TempVerificationOutcome(Enum):
    """Result of a temporary verification attempt."""
    VERIFIED = auto()        # Sufficient evidence found
    NOT_VERIFIED = auto()    # Evidence missing or invalid
    EXPIRED = auto()         # Request arrived too late


# ---------------------------------------------------------------------------
# Mock operator token list (configurable via DispatchService)
# ---------------------------------------------------------------------------

DEFAULT_VALID_OPERATOR_TOKENS: List[str] = [
    "SIM-DISPATCH-001",
    "SIM-DISPATCH-002",
]

# Mock plate → registration number lookup (Phase 2 simulation)
MOCK_PLATE_REGISTRY: Dict[str, str] = {
    "LHR-1234": "UNREG-AMB-001",
    "ISB-5678": "UNREG-AMB-002",
}


# ---------------------------------------------------------------------------
# Request dataclass
# ---------------------------------------------------------------------------

@dataclass
class TempVerificationRequest:
    """Carries all data for a temporary (unregistered) ambulance verification.

    Fields are populated before verification; result fields are set after.
    """
    # Input fields
    temp_id: str = field(default_factory=lambda: f"TEMP-{uuid.uuid4().hex[:8].upper()}")
    announced_registration: str = ""   # What the operator/app announced
    verification_method: str = ""      # "DISPATCH_OPERATOR", "AMBULANCE_APP", "LICENSE_PLATE"

    # DISPATCH_OPERATOR specific
    operator_token: str = ""
    verifying_operator_id: str = ""

    # Location (Decision 2A: GPS_MANUAL accepted)
    gps_latitude: Optional[float] = None
    gps_longitude: Optional[float] = None
    manual_location_description: str = ""  # e.g. "approaching J1 from north"
    gps_source: str = "DEVICE"             # "DEVICE" | "MANUAL" | "SIMULATED"

    # Destination
    hospital_id: str = ""
    emergency_description: str = ""

    # AMBULANCE_APP specific
    app_payload_complete: bool = False   # True if all required app fields provided

    # LICENSE_PLATE specific
    plate_number: str = ""

    # Result fields (set by TempVerifier.verify())
    outcome: TempVerificationOutcome = TempVerificationOutcome.NOT_VERIFIED
    confidence: VerificationConfidence = VerificationConfidence.NONE
    method_enum: VerificationMethod = VerificationMethod.NONE
    verified_at: Optional[float] = None
    expires_at: Optional[float] = None
    failure_reason: str = ""
    created_at: float = field(default_factory=time.time)

    def is_verified(self) -> bool:
        """Return True if verification succeeded."""
        return self.outcome == TempVerificationOutcome.VERIFIED


# ---------------------------------------------------------------------------
# Verifier
# ---------------------------------------------------------------------------

class TempVerifier:
    """Evaluates a TempVerificationRequest and sets its result fields.

    Args:
        valid_operator_tokens:   List of acceptable operator tokens.
        plate_registry:          Mock plate-number lookup dict.
        expiry_s:                Seconds from verification until temp record expires.
    """

    def __init__(
        self,
        valid_operator_tokens: Optional[List[str]] = None,
        plate_registry: Optional[Dict[str, str]] = None,
        expiry_s: float = 180.0,
    ) -> None:
        self._tokens: List[str] = (
            valid_operator_tokens
            if valid_operator_tokens is not None
            else list(DEFAULT_VALID_OPERATOR_TOKENS)
        )
        self._plate_registry: Dict[str, str] = (
            plate_registry if plate_registry is not None else dict(MOCK_PLATE_REGISTRY)
        )
        self._expiry_s = expiry_s

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def verify(
        self, req: TempVerificationRequest, now: Optional[float] = None
    ) -> TempVerificationRequest:
        """Verify the request and set result fields in-place. Returns the request.

        Every attempt is logged, including failures.

        Args:
            req: TempVerificationRequest with input fields populated.
            now: Override for current epoch time (for testing).

        Returns:
            The same request object with outcome and result fields set.
        """
        if now is None:
            now = time.time()

        method = req.verification_method.upper().strip()

        if method == "DISPATCH_OPERATOR":
            self._verify_dispatch_operator(req, now)
        elif method == "AMBULANCE_APP":
            self._verify_ambulance_app(req, now)
        elif method == "LICENSE_PLATE":
            self._verify_license_plate(req, now)
        else:
            req.outcome = TempVerificationOutcome.NOT_VERIFIED
            req.failure_reason = f"Unknown verification method: {req.verification_method!r}"
            logger.warning("[temp_verify] %s unknown method: %s", req.temp_id, method)

        logger.info(
            "[temp_verify] %s method=%s outcome=%s confidence=%s reason=%s",
            req.temp_id, method, req.outcome.name,
            req.confidence.name, req.failure_reason or "OK",
        )
        return req

    # ------------------------------------------------------------------
    # Method-specific handlers
    # ------------------------------------------------------------------

    def _verify_dispatch_operator(
        self, req: TempVerificationRequest, now: float
    ) -> None:
        """DISPATCH_OPERATOR: validate token against approved list → HIGH confidence."""
        if not req.operator_token:
            req.outcome = TempVerificationOutcome.NOT_VERIFIED
            req.failure_reason = "operator_token is empty"
            return

        if req.operator_token not in self._tokens:
            req.outcome = TempVerificationOutcome.NOT_VERIFIED
            req.failure_reason = f"operator_token {req.operator_token!r} not in approved list"
            return

        if not self._has_location(req):
            req.outcome = TempVerificationOutcome.NOT_VERIFIED
            req.failure_reason = "location missing (GPS or manual_location_description required)"
            return

        if not req.hospital_id:
            req.outcome = TempVerificationOutcome.NOT_VERIFIED
            req.failure_reason = "hospital_id required for DISPATCH_OPERATOR verification"
            return

        req.outcome = TempVerificationOutcome.VERIFIED
        req.confidence = VerificationConfidence.HIGH
        req.method_enum = VerificationMethod.DISPATCH_OPERATOR
        req.verified_at = now
        req.expires_at = now + self._expiry_s
        if req.gps_latitude is None:
            req.gps_source = "MANUAL"   # Decision 2A

    def _verify_ambulance_app(
        self, req: TempVerificationRequest, now: float
    ) -> None:
        """AMBULANCE_APP: all required fields must be present → MEDIUM confidence."""
        missing = []
        if not req.announced_registration:
            missing.append("announced_registration")
        if not self._has_location(req):
            missing.append("gps_latitude/gps_longitude or manual_location_description")
        if not req.hospital_id:
            missing.append("hospital_id")
        if not req.emergency_description:
            missing.append("emergency_description")

        if missing:
            req.outcome = TempVerificationOutcome.NOT_VERIFIED
            req.failure_reason = f"Missing required fields: {missing}"
            return

        req.outcome = TempVerificationOutcome.VERIFIED
        req.confidence = VerificationConfidence.MEDIUM
        req.method_enum = VerificationMethod.AMBULANCE_APP
        req.verified_at = now
        req.expires_at = now + self._expiry_s
        if req.gps_latitude is None:
            req.gps_source = "MANUAL"   # Decision 2A

    def _verify_license_plate(
        self, req: TempVerificationRequest, now: float
    ) -> None:
        """LICENSE_PLATE: plate looked up in mock dict → LOW confidence if found."""
        plate = req.plate_number.strip()
        if not plate:
            req.outcome = TempVerificationOutcome.NOT_VERIFIED
            req.failure_reason = "plate_number is empty"
            return

        match = self._plate_registry.get(plate)
        if match is None:
            req.outcome = TempVerificationOutcome.NOT_VERIFIED
            req.failure_reason = f"Plate {plate!r} not found in mock registry"
            return

        req.outcome = TempVerificationOutcome.VERIFIED
        req.confidence = VerificationConfidence.LOW
        req.method_enum = VerificationMethod.LICENSE_PLATE
        req.verified_at = now
        req.expires_at = now + self._expiry_s
        if req.gps_latitude is None:
            req.gps_source = "MANUAL"   # Decision 2A
        # Override announced_registration with the plate-matched one
        if not req.announced_registration:
            req.announced_registration = match
        logger.info(
            "[temp_verify] Plate %s matched to registration %s", plate, match
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _has_location(req: TempVerificationRequest) -> bool:
        """Return True if any form of location is provided (GPS or manual)."""
        gps_ok = req.gps_latitude is not None and req.gps_longitude is not None
        manual_ok = bool(req.manual_location_description.strip())
        return gps_ok or manual_ok

