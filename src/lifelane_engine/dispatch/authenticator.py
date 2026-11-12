"""
authenticator.py — Ambulance device authentication for LifeLane.

Validates device credentials against the registry.
No plaintext secrets are compared — only SHA-256 hashes.

SAFETY RULE: Authentication is a prerequisite for entering the dispatch
             workflow; it does NOT by itself grant signal priority.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from lifelane_engine.dispatch.registry import AmbulanceRegistry, RegistrationStatus, hash_credential

logger = logging.getLogger(__name__)


@dataclass
class AuthResult:
    """Result of an authentication attempt."""
    success: bool
    ambulance_id: str         # LifeLane ID (or "" on failure)
    device_id: str            # device_id that was presented
    reason: str               # Human-readable explanation


class AmbulanceAuthenticator:
    """Validates device credentials against the ambulance registry.

    Usage::

        auth = AmbulanceAuthenticator(registry)
        result = auth.authenticate("DEV-001", "mock-secret-001")
        if result.success:
            ...  # proceed to dispatch
    """

    def __init__(self, registry: AmbulanceRegistry) -> None:
        self._registry = registry

    def authenticate(self, device_id: str, credential: str) -> AuthResult:
        """Authenticate an onboard LifeLane device.

        Steps:
            1. Look up device_id in registry.
            2. Check registration status is ACTIVE.
            3. Compare SHA-256 hash of supplied credential to stored hash.

        Args:
            device_id:   The device identifier presented by the ambulance.
            credential:  The plaintext credential (hashed internally before compare).

        Returns:
            AuthResult with success=True and the LifeLane ID, or
            success=False with a reason.
        """
        entry = self._registry.lookup_by_device_id(device_id)

        if entry is None:
            logger.warning("[auth] device_id=%s not found in registry", device_id)
            return AuthResult(
                success=False,
                ambulance_id="",
                device_id=device_id,
                reason=f"device_id '{device_id}' not registered",
            )

        if entry.registration_status != RegistrationStatus.ACTIVE:
            logger.warning(
                "[auth] device_id=%s registration is %s",
                device_id, entry.registration_status.name,
            )
            return AuthResult(
                success=False,
                ambulance_id=entry.lifelane_id,
                device_id=device_id,
                reason=f"Registration status is {entry.registration_status.name}, not ACTIVE",
            )

        supplied_hash = hash_credential(credential)
        if supplied_hash != entry.credential_hash:
            logger.warning("[auth] device_id=%s credential mismatch", device_id)
            return AuthResult(
                success=False,
                ambulance_id=entry.lifelane_id,
                device_id=device_id,
                reason="Credential mismatch",
            )

        logger.info(
            "[auth] Authenticated device_id=%s as lifelane_id=%s",
            device_id, entry.lifelane_id,
        )
        return AuthResult(
            success=True,
            ambulance_id=entry.lifelane_id,
            device_id=device_id,
            reason="OK",
        )

