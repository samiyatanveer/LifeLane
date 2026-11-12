"""
session_manager.py — Authenticated ambulance session management.

Each authenticated ambulance device holds at most one active session.
Sessions expire automatically and can be explicitly invalidated.

SAFETY RULE: Session validity is checked by the dispatch service before
             accepting any emergency request submission.
"""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Default session TTL from settings.yaml (overridable via constructor)
DEFAULT_SESSION_TTL_S: float = 3600.0


class DuplicateSessionError(Exception):
    """Raised when a second active session is created for the same ambulance."""


@dataclass
class Session:
    """An authenticated device session."""
    session_id: str
    ambulance_id: str          # LifeLane ID
    device_id: str
    created_at: float
    expires_at: float
    invalidated: bool = False
    invalidation_reason: str = ""

    def is_active(self, now: float) -> bool:
        """Return True if session is valid and not expired."""
        return not self.invalidated and now < self.expires_at

    def is_expired(self, now: float) -> bool:
        """Return True if session TTL has passed."""
        return now >= self.expires_at


class SessionManager:
    """Manages authenticated ambulance sessions.

    Enforces a maximum of one active session per ambulance (LifeLane ID).
    """

    def __init__(self, session_ttl_s: float = DEFAULT_SESSION_TTL_S) -> None:
        self._session_ttl_s = session_ttl_s
        self._sessions: Dict[str, Session] = {}   # session_id → Session
        # ambulance_id → session_id (for quick single-session enforcement)
        self._active_by_ambulance: Dict[str, str] = {}

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def create_session(
        self,
        ambulance_id: str,
        device_id: str,
        now: Optional[float] = None,
    ) -> Session:
        """Create a new session for an authenticated ambulance.

        Raises:
            DuplicateSessionError: if the ambulance already has an active session.
        """
        if now is None:
            now = time.time()

        existing_id = self._active_by_ambulance.get(ambulance_id)
        if existing_id is not None:
            existing = self._sessions.get(existing_id)
            if existing is not None and existing.is_active(now):
                raise DuplicateSessionError(
                    f"Ambulance {ambulance_id!r} already has active session {existing_id!r}"
                )
            # Clean up stale mapping
            self._active_by_ambulance.pop(ambulance_id, None)

        session = Session(
            session_id=str(uuid.uuid4()),
            ambulance_id=ambulance_id,
            device_id=device_id,
            created_at=now,
            expires_at=now + self._session_ttl_s,
        )
        self._sessions[session.session_id] = session
        self._active_by_ambulance[ambulance_id] = session.session_id
        logger.info(
            "[session] Created session %s for ambulance %s device %s (expires %.0f)",
            session.session_id, ambulance_id, device_id, session.expires_at,
        )
        return session

    def validate_session(self, session_id: str, now: Optional[float] = None) -> bool:
        """Return True if the session_id is active and not expired."""
        if now is None:
            now = time.time()
        session = self._sessions.get(session_id)
        if session is None:
            return False
        return session.is_active(now)

    def invalidate_session(
        self,
        session_id: str,
        reason: str = "explicit invalidation",
        now: Optional[float] = None,
    ) -> bool:
        """Invalidate a session. Returns False if not found."""
        if now is None:
            now = time.time()
        session = self._sessions.get(session_id)
        if session is None:
            logger.warning("[session] invalidate: session_id=%s not found", session_id)
            return False
        session.invalidated = True
        session.invalidation_reason = reason
        self._active_by_ambulance.pop(session.ambulance_id, None)
        logger.info("[session] Invalidated session %s: %s", session_id, reason)
        return True

    def get_active_session(
        self, ambulance_id: str, now: Optional[float] = None
    ) -> Optional[Session]:
        """Return the currently active session for an ambulance, or None."""
        if now is None:
            now = time.time()
        session_id = self._active_by_ambulance.get(ambulance_id)
        if session_id is None:
            return None
        session = self._sessions.get(session_id)
        if session is None or not session.is_active(now):
            self._active_by_ambulance.pop(ambulance_id, None)
            return None
        return session

    def cleanup_expired(self, now: Optional[float] = None) -> List[str]:
        """Remove expired sessions. Returns list of removed session_ids."""
        if now is None:
            now = time.time()
        expired = [
            sid for sid, s in self._sessions.items() if s.is_expired(now)
        ]
        for sid in expired:
            session = self._sessions.pop(sid)
            self._active_by_ambulance.pop(session.ambulance_id, None)
        if expired:
            logger.info("[session] Cleaned up %d expired session(s)", len(expired))
        return expired

    def get_session(self, session_id: str) -> Optional[Session]:
        """Return a session by ID regardless of status."""
        return self._sessions.get(session_id)

