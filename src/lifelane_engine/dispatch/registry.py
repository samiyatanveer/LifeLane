"""
registry.py — Ambulance Registry for LifeLane.

Maintains a dict-backed in-memory registry of registered ambulances.
In Phase 7+ this will be backed by PostgreSQL.

No plaintext credentials are stored — only SHA-256 hashes.
"""
from __future__ import annotations

import hashlib
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class RegistrationStatus(Enum):
    """Lifecycle status of an ambulance's registry entry."""
    ACTIVE = auto()
    SUSPENDED = auto()
    REVOKED = auto()


@dataclass
class AmbulanceEntry:
    """A single ambulance registration record.

    Credentials are stored as SHA-256 hex digests; never as plaintext.
    """
    lifelane_id: str              # Unique LifeLane-assigned identifier (e.g. "LL-001")
    registration_number: str      # Vehicle registration plate (e.g. "RES-123")
    service_name: str             # Owning emergency service (e.g. "City EMS")
    device_id: str                # Onboard device ID used for authentication
    credential_hash: str          # SHA-256 hex of the device's secret credential
    registration_status: RegistrationStatus = field(
        default=RegistrationStatus.ACTIVE
    )
    registered_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    notes: str = ""

    def is_active(self) -> bool:
        """Return True if the registration is ACTIVE."""
        return self.registration_status == RegistrationStatus.ACTIVE


class AmbulanceRegistry:
    """In-memory ambulance registry.

    Keyed internally by lifelane_id. Supports lookup by device_id,
    registration_number, or lifelane_id.
    """

    def __init__(self) -> None:
        self._entries: Dict[str, AmbulanceEntry] = {}  # lifelane_id → entry

    # ------------------------------------------------------------------
    # Mutating operations
    # ------------------------------------------------------------------

    def register(self, entry: AmbulanceEntry) -> None:
        """Add or overwrite an ambulance registration entry."""
        if entry.lifelane_id in self._entries:
            logger.warning(
                "[registry] Overwriting existing entry for lifelane_id=%s", entry.lifelane_id
            )
        self._entries[entry.lifelane_id] = entry
        logger.info(
            "[registry] Registered ambulance lifelane_id=%s reg=%s device=%s",
            entry.lifelane_id, entry.registration_number, entry.device_id,
        )

    def update_status(
        self, lifelane_id: str, status: RegistrationStatus, notes: str = ""
    ) -> bool:
        """Update the registration status of an ambulance. Returns False if not found."""
        entry = self._entries.get(lifelane_id)
        if entry is None:
            logger.warning("[registry] update_status: lifelane_id=%s not found", lifelane_id)
            return False
        entry.registration_status = status
        entry.updated_at = time.time()
        entry.notes = notes or entry.notes
        logger.info("[registry] Updated status lifelane_id=%s → %s", lifelane_id, status.name)
        return True

    # ------------------------------------------------------------------
    # Lookup operations
    # ------------------------------------------------------------------

    def lookup_by_lifelane_id(self, lifelane_id: str) -> Optional[AmbulanceEntry]:
        """Look up by LifeLane ID."""
        return self._entries.get(lifelane_id)

    def lookup_by_device_id(self, device_id: str) -> Optional[AmbulanceEntry]:
        """Find the first entry with a matching device_id."""
        for entry in self._entries.values():
            if entry.device_id == device_id:
                return entry
        return None

    def lookup_by_registration(self, registration_number: str) -> Optional[AmbulanceEntry]:
        """Find the first entry with a matching registration plate."""
        for entry in self._entries.values():
            if entry.registration_number == registration_number:
                return entry
        return None

    def list_all(self) -> List[AmbulanceEntry]:
        """Return all registered ambulances."""
        return list(self._entries.values())

    def __len__(self) -> int:
        return len(self._entries)


# ---------------------------------------------------------------------------
# Credential helper
# ---------------------------------------------------------------------------

def hash_credential(credential: str) -> str:
    """Return the SHA-256 hex digest of a credential string.

    Never store plaintext credentials. Always hash before registering or
    comparing.
    """
    return hashlib.sha256(credential.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Mock registry factory
# ---------------------------------------------------------------------------

class MockRegistry:
    """Factory for a pre-seeded mock AmbulanceRegistry used in tests and POC."""

    # Deterministic mock credentials — only the hashes are stored
    _MOCK_CREDENTIALS: Dict[str, str] = {
        "DEV-001": "mock-secret-001",
        "DEV-002": "mock-secret-002",
    }

    @classmethod
    def build_default(cls) -> AmbulanceRegistry:
        """Build a mock registry with two pre-seeded ambulances.

        Ambulance 1 (AMB-001 / DEV-001): Active, City EMS
        Ambulance 2 (AMB-002 / DEV-002): Active, North EMS
        """
        registry = AmbulanceRegistry()
        ts = 1_000_000.0  # Fixed timestamp for deterministic tests

        registry.register(AmbulanceEntry(
            lifelane_id="LL-001",
            registration_number="AMB-001",
            service_name="City EMS",
            device_id="DEV-001",
            credential_hash=hash_credential(cls._MOCK_CREDENTIALS["DEV-001"]),
            registration_status=RegistrationStatus.ACTIVE,
            registered_at=ts,
            updated_at=ts,
            notes="Mock ambulance 1 — Phase 2 POC",
        ))

        registry.register(AmbulanceEntry(
            lifelane_id="LL-002",
            registration_number="AMB-002",
            service_name="North EMS",
            device_id="DEV-002",
            credential_hash=hash_credential(cls._MOCK_CREDENTIALS["DEV-002"]),
            registration_status=RegistrationStatus.ACTIVE,
            registered_at=ts,
            updated_at=ts,
            notes="Mock ambulance 2 — Phase 2 POC",
        ))

        logger.info("[registry] MockRegistry.build_default() created 2 ambulances")
        return registry

    @classmethod
    def mock_credential(cls, device_id: str) -> str:
        """Return the plaintext mock credential for a given device_id."""
        return cls._MOCK_CREDENTIALS[device_id]

