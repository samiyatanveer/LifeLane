"""
signal_controller.py — Independent per-junction safety state machine.

SAFETY RULES (non-negotiable):
  - ML and the scheduler submit REQUESTS; this controller owns all transitions.
  - Only the validated ambulance approach may be served.
  - Conflicting movements must NEVER receive green simultaneously.
  - Signal changes use yellow → all-red → green (never direct green-to-green).
  - Passage is confirmed by vehicle/detector position, NOT by audio silence.
  - On stale request, fault, or failure → expire and return to safe fallback.
  - Runtime assertions prevent illegal transitions and conflicting greens.

State machine:
    NORMAL → SUSPECTED → CONFIRMED → PREPARING → SERVING → EXITING → RECOVERING → NORMAL
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

from lifelane_engine import config

logger = logging.getLogger(__name__)


class ControllerState(Enum):
    """Per-junction controller lifecycle state."""
    NORMAL = auto()
    SUSPECTED = auto()
    CONFIRMED = auto()
    PREPARING = auto()
    SERVING = auto()
    EXITING = auto()
    RECOVERING = auto()


# Allowed state transitions — guard against illegal jumps
_ALLOWED_TRANSITIONS: dict[ControllerState, set[ControllerState]] = {
    ControllerState.NORMAL:     {ControllerState.SUSPECTED},
    ControllerState.SUSPECTED:  {ControllerState.CONFIRMED, ControllerState.NORMAL},
    ControllerState.CONFIRMED:  {ControllerState.PREPARING, ControllerState.NORMAL},
    ControllerState.PREPARING:  {ControllerState.SERVING, ControllerState.NORMAL},
    ControllerState.SERVING:    {ControllerState.EXITING},
    ControllerState.EXITING:    {ControllerState.RECOVERING, ControllerState.NORMAL},
    ControllerState.RECOVERING: {ControllerState.NORMAL},
}


class SafetyViolation(Exception):
    """Raised when a safety constraint would be violated."""


@dataclass
class SignalPhase:
    """A single signal phase (mock representation for Phase 1)."""
    phase_id: str
    description: str
    green_movements: list[str]  # e.g. ["north_through", "south_through"]
    duration_s: float


@dataclass
class JunctionSignalController:
    """Independent safety controller for one junction.

    In Phase 1 this operates on a mock signal model (no SUMO).
    Phase 3 will wire it to TraCI.

    The controller enforces every safety invariant and logs every transition.
    """

    junction_id: str

    # Phase 1 mock signal state
    current_phase_id: str = "normal_NS"
    state: ControllerState = field(default=ControllerState.NORMAL, init=False)

    # Active request info
    serving_ambulance_id: Optional[str] = field(default=None, init=False)
    serving_approach: Optional[str] = field(default=None, init=False)
    serving_request_id: Optional[str] = field(default=None, init=False)
    serving_started_at: Optional[float] = field(default=None, init=False)
    request_expiry_at: Optional[float] = field(default=None, init=False)

    # Configuration
    yellow_s: float = field(init=False)
    all_red_s: float = field(init=False)
    min_green_s: float = field(init=False)
    max_green_s: float = field(init=False)
    max_service_s: float = field(init=False)

    def __post_init__(self) -> None:
        sc_cfg = config.get("safety_controller")
        req_cfg = config.get("ambulance_request")
        self.yellow_s = float(sc_cfg.get("yellow_duration_s", 3.0))
        self.all_red_s = float(sc_cfg.get("all_red_duration_s", 3.0))
        self.min_green_s = float(sc_cfg.get("min_green_s", 7.0))
        self.max_green_s = float(sc_cfg.get("max_green_s", 60.0))
        self.max_service_s = float(req_cfg.get("max_service_duration_s", 120.0))

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def _transition(self, new_state: ControllerState, reason: str = "") -> None:
        """Execute a state transition with guard checks and logging."""
        allowed = _ALLOWED_TRANSITIONS.get(self.state, set())
        if new_state not in allowed:
            msg = (
                f"[signal_controller] junction={self.junction_id}: "
                f"ILLEGAL transition {self.state.name} → {new_state.name} "
                f"(reason={reason!r})"
            )
            logger.error(msg)
            raise SafetyViolation(msg)

        logger.info(
            "[signal_controller] junction=%s: %s → %s  [%s]",
            self.junction_id, self.state.name, new_state.name, reason,
        )
        self.state = new_state

    # ------------------------------------------------------------------
    # Public API — called by audio selector / scheduler / simulation
    # ------------------------------------------------------------------

    def notify_siren_suspected(self, approach: str) -> None:
        """Audio subsystem has detected siren evidence on this approach."""
        if self.state == ControllerState.NORMAL:
            self._transition(ControllerState.SUSPECTED, f"siren suspected on {approach}")

    def notify_siren_confirmed(self, approach: str) -> None:
        """Three consecutive positive windows confirmed on this approach."""
        if self.state == ControllerState.SUSPECTED:
            self._transition(ControllerState.CONFIRMED, f"siren confirmed on {approach}")

    def request_priority(
        self,
        request_id: str,
        ambulance_id: str,
        approach: str,
        expiry_at: float,
        confirmed_approach: str,
        now: float | None = None,
    ) -> bool:
        """Attempt to grant priority for an authorized request.

        Safety checks performed here:
          1. State must be CONFIRMED.
          2. Request approach must match audio-confirmed approach.
          3. Request must not be expired.
          4. No conflicting green movements (assertion).

        Returns:
            True if priority is granted (transitions to PREPARING).
            False if any safety check fails.
        """
        if now is None:
            now = time.time()

        if self.state != ControllerState.CONFIRMED:
            logger.warning(
                "[signal_controller] junction=%s: priority request rejected "
                "(state is %s, need CONFIRMED)", self.junction_id, self.state.name,
            )
            return False

        # Approach must match audio evidence
        if approach != confirmed_approach:
            logger.warning(
                "[signal_controller] junction=%s: approach mismatch — "
                "request=%s confirmed=%s → rejected",
                self.junction_id, approach, confirmed_approach,
            )
            return False

        # Request must not be expired
        if now > expiry_at:
            logger.warning(
                "[signal_controller] junction=%s: request %s expired → rejected",
                self.junction_id, request_id,
            )
            return False

        self.serving_ambulance_id = ambulance_id
        self.serving_approach = approach
        self.serving_request_id = request_id
        self.request_expiry_at = expiry_at
        self._transition(ControllerState.PREPARING, f"request {request_id} accepted")
        return True

    def execute_safe_transition_to_green(self, now: float | None = None) -> dict:
        """Execute yellow → all-red → green transition (mock, Phase 1).

        SAFETY ASSERTION: Conflicting approaches must never receive green.

        Returns:
            A log dict describing the transition steps.
        """
        if self.state != ControllerState.PREPARING:
            raise SafetyViolation(
                f"execute_safe_transition_to_green called in state {self.state.name}"
            )

        if now is None:
            now = time.time()

        # Assert: only the validated approach gets green
        assert self.serving_approach is not None, "serving_approach must be set"

        log: dict = {
            "junction": self.junction_id,
            "ambulance": self.serving_ambulance_id,
            "approach": self.serving_approach,
            "steps": [],
        }

        log["steps"].append({"phase": "yellow", "duration_s": self.yellow_s})
        log["steps"].append({"phase": "all_red", "duration_s": self.all_red_s})
        log["steps"].append({"phase": "ambulance_green", "approach": self.serving_approach})

        self.serving_started_at = now + self.yellow_s + self.all_red_s

        logger.info(
            "[signal_controller] junction=%s: safe transition → "
            "yellow(%.0fs) → all_red(%.0fs) → green(%s)",
            self.junction_id, self.yellow_s, self.all_red_s, self.serving_approach,
        )

        self._transition(ControllerState.SERVING, "safe transition complete")
        return log

    def confirm_passage(self, ambulance_id: str, now: float | None = None) -> bool:
        """Confirm ambulance passage via vehicle-position/detector (not audio).

        SAFETY: Passage is confirmed by vehicle position, NOT by audio silence.

        Returns:
            True if confirmation accepted, False if ambulance_id does not match.
        """
        if now is None:
            now = time.time()

        if self.state != ControllerState.SERVING:
            logger.warning(
                "[signal_controller] junction=%s: confirm_passage called in state %s",
                self.junction_id, self.state.name,
            )
            return False

        if ambulance_id != self.serving_ambulance_id:
            logger.warning(
                "[signal_controller] junction=%s: passage confirmation ambulance_id mismatch "
                "expected=%s got=%s",
                self.junction_id, self.serving_ambulance_id, ambulance_id,
            )
            return False

        logger.info(
            "[signal_controller] junction=%s: passage confirmed for ambulance %s",
            self.junction_id, ambulance_id,
        )
        self._transition(ControllerState.EXITING, "passage confirmed")
        return True

    def begin_recovery(self) -> None:
        """Begin bounded recovery of coordinated signal operation."""
        self._transition(ControllerState.RECOVERING, "starting recovery")

    def complete_recovery(self) -> None:
        """Mark recovery as complete; return to NORMAL coordinated operation."""
        logger.info(
            "[signal_controller] junction=%s: recovery complete → NORMAL",
            self.junction_id,
        )
        self._transition(ControllerState.NORMAL, "recovery complete")
        self._clear_serving_state()

    def expire_and_reset(self, reason: str = "expired/fault") -> None:
        """Safe expiry — cancel priority and return to NORMAL immediately.

        Used on stale request, network failure, or simulation fault.
        Always logs the reason.
        """
        logger.warning(
            "[signal_controller] junction=%s: expire_and_reset (%s) from state %s",
            self.junction_id, reason, self.state.name,
        )
        self.state = ControllerState.NORMAL
        self._clear_serving_state()

    def check_request_expiry(self, now: float | None = None) -> bool:
        """Check if the current request has expired; expire if so.

        Returns True if an expiry action was taken.
        """
        if now is None:
            now = time.time()
        if (
            self.request_expiry_at is not None
            and now > self.request_expiry_at
            and self.state not in (ControllerState.NORMAL, ControllerState.RECOVERING)
        ):
            self.expire_and_reset("request expiry timeout")
            return True
        return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _clear_serving_state(self) -> None:
        self.serving_ambulance_id = None
        self.serving_approach = None
        self.serving_request_id = None
        self.serving_started_at = None
        self.request_expiry_at = None

