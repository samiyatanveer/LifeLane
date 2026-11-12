"""
corridor_scheduler.py — Route-aware corridor preparation scheduler.

The scheduler watches ambulance ETA predictions and issues time-limited
preparation requests to upcoming junctions via the safety controller.

SAFETY:
  - The scheduler submits REQUESTS; it never commands green directly.
  - The independent safety controller authorizes all signal transitions.
  - Requests carry expiry times; stale requests are cancelled safely.

Phase 1: mock implementation with placeholder ETA (no SUMO/model).
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from lifelane_engine import config

logger = logging.getLogger(__name__)


@dataclass
class PreparationRequest:
    """A time-limited signal-preparation request issued to a junction."""
    junction_id: str
    ambulance_id: str
    approach: str
    issued_at: float
    expires_at: float
    predicted_eta_s: float
    issued: bool = False
    cancelled: bool = False
    confirmed: bool = False


class CorridorScheduler:
    """Manages preparation requests for a sequence of junctions along a route.

    Usage:
        scheduler = CorridorScheduler(junctions=["J1", "J2", "J4"])
        scheduler.update(current_junction="J1", predicted_eta=25.0, now=t)
    """

    def __init__(
        self,
        junctions: List[str],
        ambulance_id: str,
        approach_by_junction: Dict[str, str],
        on_prepare: Optional[Callable[[PreparationRequest], None]] = None,
    ) -> None:
        """
        Args:
            junctions:            Ordered list of junction IDs on the route.
            ambulance_id:         Ambulance being served.
            approach_by_junction: Maps junction_id → approach direction.
            on_prepare:           Callback invoked when a preparation is issued.
        """
        corridor_cfg = config.get("corridor")
        sc_cfg = config.get("safety_controller")

        self.junctions = junctions
        self.ambulance_id = ambulance_id
        self.approach_by_junction = approach_by_junction
        self.on_prepare = on_prepare

        self.safety_margin_s: float = float(corridor_cfg.get("safety_margin_s", 5.0))
        self.safe_transition_s: float = float(corridor_cfg.get("safe_transition_time_s", 6.0))

        self._requests: Dict[str, PreparationRequest] = {}

    def _preparation_time(
        self,
        predicted_eta_s: float,
        predicted_queue_clearance_s: float = 0.0,
    ) -> float:
        """Compute how many seconds before ETA we should start preparation.

        preparation_time = predicted_ETA
                         - safe_transition_time
                         - predicted_queue_clearance_time
                         - safety_margin
        """
        return (
            predicted_eta_s
            - self.safe_transition_s
            - predicted_queue_clearance_s
            - self.safety_margin_s
        )

    def update(
        self,
        current_junction: str,
        predicted_eta_s: float,
        now: float | None = None,
        predicted_queue_clearance_s: float = 0.0,
    ) -> Optional[PreparationRequest]:
        """Check if preparation should be issued for the current junction.

        If preparation_time <= 0, issue preparation now.
        Otherwise keep monitoring.

        Returns:
            The PreparationRequest if issued, else None.
        """
        if now is None:
            now = time.time()

        if current_junction not in self.junctions:
            logger.warning(
                "[scheduler] junction %s not in corridor %s",
                current_junction, self.junctions,
            )
            return None

        # Check if request already issued
        existing = self._requests.get(current_junction)
        if existing and (existing.issued or existing.cancelled):
            if existing.cancelled:
                return None
            return existing

        approach = self.approach_by_junction.get(current_junction, "north")
        prep_time = self._preparation_time(predicted_eta_s, predicted_queue_clearance_s)

        logger.debug(
            "[scheduler] junction=%s ETA=%.1fs prep_time=%.1fs",
            current_junction, predicted_eta_s, prep_time,
        )

        if prep_time <= 0:
            # Issue preparation immediately
            expiry_at = now + predicted_eta_s + self.safety_margin_s
            req = PreparationRequest(
                junction_id=current_junction,
                ambulance_id=self.ambulance_id,
                approach=approach,
                issued_at=now,
                expires_at=expiry_at,
                predicted_eta_s=predicted_eta_s,
                issued=True,
            )
            self._requests[current_junction] = req
            logger.info(
                "[scheduler] Issued preparation for junction=%s approach=%s ETA=%.1fs",
                current_junction, approach, predicted_eta_s,
            )
            if self.on_prepare:
                self.on_prepare(req)
            return req

        return None

    def cancel(self, junction_id: str, reason: str = "") -> None:
        """Safely cancel an issued preparation request."""
        req = self._requests.get(junction_id)
        if req and not req.confirmed:
            req.cancelled = True
            logger.warning(
                "[scheduler] Cancelled preparation for junction=%s: %s",
                junction_id, reason,
            )

    def confirm(self, junction_id: str) -> None:
        """Mark passage confirmed at a junction."""
        req = self._requests.get(junction_id)
        if req:
            req.confirmed = True
            logger.info(
                "[scheduler] Passage confirmed at junction=%s", junction_id,
            )

    def check_expirations(self, now: float | None = None) -> List[str]:
        """Cancel expired unconfirmed requests. Returns list of cancelled junction IDs."""
        if now is None:
            now = time.time()
        cancelled = []
        for jid, req in self._requests.items():
            if req.issued and not req.confirmed and not req.cancelled:
                if now > req.expires_at:
                    self.cancel(jid, "preparation request expired")
                    cancelled.append(jid)
        return cancelled

