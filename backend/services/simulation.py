"""Signal simulation service — in-memory junction state machine."""
from __future__ import annotations

import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Junction states
STATES = ["NORMAL", "SUSPECTED", "CONFIRMED", "PREPARING", "SERVING", "EXITING", "RECOVERING"]

JUNCTION_IDS = ["J1", "J2", "J3", "J4"]

VALID_ACTIONS = ["request_priority", "confirm_passage", "cancel", "reset"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


class JunctionState:
    def __init__(self, junction_id: str) -> None:
        self.junction_id = junction_id
        self.state: str = "NORMAL"
        self.approach: Optional[str] = None
        self.ambulance_id: Optional[str] = None
        self.since: datetime = _now()


class SimulationService:
    def __init__(self) -> None:
        self._junctions: dict[str, JunctionState] = {
            jid: JunctionState(jid) for jid in JUNCTION_IDS
        }
        self._events: list[dict] = []

    def _log_event(
        self,
        junction_id: str,
        from_state: str,
        to_state: str,
        trigger: str,
        ambulance_id: Optional[str] = None,
        approach: Optional[str] = None,
    ) -> dict:
        event = {
            "id": str(uuid.uuid4()),
            "junction_id": junction_id,
            "from_state": from_state,
            "to_state": to_state,
            "trigger": trigger,
            "ambulance_id": ambulance_id,
            "approach": approach,
            "is_simulation": True,
            "created_at": _now(),
        }
        self._events.append(event)
        if len(self._events) > 200:
            self._events = self._events[-200:]
        return event

    def _transition(
        self,
        js: JunctionState,
        new_state: str,
        trigger: str,
        ambulance_id: Optional[str] = None,
        approach: Optional[str] = None,
    ) -> None:
        old_state = js.state
        js.state = new_state
        js.ambulance_id = ambulance_id
        js.approach = approach
        js.since = _now()
        self._log_event(js.junction_id, old_state, new_state, trigger, ambulance_id, approach)
        logger.info("Junction %s: %s → %s (trigger=%s)", js.junction_id, old_state, new_state, trigger)

    def get_all_junctions(self) -> list[dict]:
        return [self._junction_dict(js) for js in self._junctions.values()]

    def _junction_dict(self, js: JunctionState) -> dict:
        return {
            "junction_id": js.junction_id,
            "state": js.state,
            "approach": js.approach,
            "ambulance_id": js.ambulance_id,
            "since": js.since,
            "is_simulation": True,
        }

    def simulate_action(
        self,
        junction_id: str,
        action: str,
        ambulance_id: Optional[str] = None,
        approach: Optional[str] = None,
    ) -> dict:
        if junction_id not in self._junctions:
            raise ValueError(f"Unknown junction: {junction_id}")
        if action not in VALID_ACTIONS:
            raise ValueError(f"Invalid action '{action}'. Valid: {VALID_ACTIONS}")

        js = self._junctions[junction_id]
        current = js.state

        if action == "request_priority":
            if current in ("NORMAL", "SUSPECTED", "CONFIRMED"):
                # Log PREPARING intermediate step
                self._log_event(js.junction_id, current, "PREPARING", action, ambulance_id, approach)
                self._transition(js, "SERVING", action, ambulance_id, approach)
            else:
                # Already serving/recovering — no-op, just return current
                pass

        elif action == "confirm_passage":
            if current == "SERVING":
                self._transition(js, "RECOVERING", action, ambulance_id, approach)
                # Auto-recover to NORMAL
                old = js.state
                js.state = "NORMAL"
                js.ambulance_id = None
                js.approach = None
                js.since = _now()
                self._log_event(js.junction_id, old, "NORMAL", "auto_recover", ambulance_id, approach)

        elif action in ("cancel", "reset"):
            if current != "NORMAL":
                self._transition(js, "NORMAL", action, None, None)
                js.ambulance_id = None
                js.approach = None

        return {
            "junction_id": js.junction_id,
            "state": js.state,
            "approach": js.approach,
            "ambulance_id": js.ambulance_id,
            "since": js.since,
            "is_simulation": True,
            "transitions_logged": len(self._events),
        }

    def get_events(self) -> list[dict]:
        return list(reversed(self._events))

    def get_stats(self) -> dict:
        serving = sum(1 for js in self._junctions.values() if js.state != "NORMAL")
        return {
            "active_junctions": serving,
            "signal_events": len(self._events),
            "junction_states": {jid: js.state for jid, js in self._junctions.items()},
        }


# ── Singleton ─────────────────────────────────────────────────────────────────

_service: SimulationService | None = None


def get_simulation_service() -> SimulationService:
    global _service
    if _service is None:
        _service = SimulationService()
    return _service
