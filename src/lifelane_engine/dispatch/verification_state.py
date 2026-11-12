"""
verification_state.py — Three-tier ambulance verification state definitions.

States (in escalating order):
    UNDETECTED  — no siren detected
    DETECTED    — siren detected, approach identified; NO signal priority granted
    VERIFIED    — ambulance identity and emergency confirmed via an approved method
    AUTHORIZED  — safety controller approved; route-aware signal priority active

SAFETY RULE: The signal safety controller checks authorization level before
             granting any green phase. DETECTED alone is never sufficient.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


class VerificationLevel(Enum):
    """Three-tier ambulance verification level (+ UNDETECTED baseline)."""
    UNDETECTED = auto()   # No siren detected yet
    DETECTED = auto()     # Siren detected + approach identified (no priority)
    VERIFIED = auto()     # Identity/emergency verified; awaiting safety approval
    AUTHORIZED = auto()   # Safety controller approved; priority active


class VerificationConfidence(Enum):
    """Confidence of the verification decision."""
    HIGH = auto()    # e.g. registered device credential + DISPATCH_OPERATOR token
    MEDIUM = auto()  # e.g. AMBULANCE_APP with full payload
    LOW = auto()     # e.g. LICENSE_PLATE lookup only
    NONE = auto()    # Not verified


class VerificationMethod(Enum):
    """How the ambulance was verified."""
    REGISTERED_DEVICE = auto()      # Authenticated onboard LifeLane device
    DISPATCH_OPERATOR = auto()      # Authorized dispatch operator token
    AMBULANCE_APP = auto()          # Ambulance-side app with full payload
    LICENSE_PLATE = auto()          # License plate lookup (lowest confidence)
    NONE = auto()                   # Not yet verified


@dataclass
class VerificationRecord:
    """Tracks the current verification state of an ambulance at a junction.

    One record exists per active detection event. It is created when a siren is
    detected (DETECTED) and escalated as verification evidence arrives.
    """
    ambulance_id: str
    is_registered: bool
    verification_level: VerificationLevel = field(default=VerificationLevel.DETECTED)
    verification_method: VerificationMethod = field(default=VerificationMethod.NONE)
    verification_confidence: VerificationConfidence = field(
        default=VerificationConfidence.NONE
    )
    verified_at: Optional[float] = None       # epoch timestamp of verification
    expires_at: Optional[float] = None        # when this record should be discarded
    approach: Optional[str] = None            # e.g. "north"
    junction_id: Optional[str] = None         # junction where siren was detected
    detection_timestamp: float = field(default=0.0)  # epoch when DETECTED set

    def is_expired(self, now: float) -> bool:
        """Return True if the verification record has passed its expiry."""
        if self.expires_at is None:
            return False
        return now > self.expires_at

    def can_authorize(self) -> bool:
        """Return True if the record is at VERIFIED level or above.

        Note: actual authorization requires the safety controller's approval.
        This only checks that the minimum evidence threshold is met.
        """
        return self.verification_level in (
            VerificationLevel.VERIFIED,
            VerificationLevel.AUTHORIZED,
        )

    def escalate_to_verified(
        self,
        method: VerificationMethod,
        confidence: VerificationConfidence,
        verified_at: float,
        expires_at: float,
    ) -> None:
        """Escalate from DETECTED to VERIFIED."""
        if self.verification_level == VerificationLevel.UNDETECTED:
            raise ValueError("Cannot verify from UNDETECTED state; must be DETECTED first")
        self.verification_level = VerificationLevel.VERIFIED
        self.verification_method = method
        self.verification_confidence = confidence
        self.verified_at = verified_at
        self.expires_at = expires_at

    def escalate_to_authorized(self) -> None:
        """Escalate from VERIFIED to AUTHORIZED (called by safety controller)."""
        if self.verification_level != VerificationLevel.VERIFIED:
            raise ValueError(
                f"Cannot authorize from {self.verification_level.name}; must be VERIFIED"
            )
        self.verification_level = VerificationLevel.AUTHORIZED

    def __repr__(self) -> str:
        return (
            f"VerificationRecord(amb={self.ambulance_id!r}, "
            f"level={self.verification_level.name}, "
            f"method={self.verification_method.name}, "
            f"junction={self.junction_id!r})"
        )

