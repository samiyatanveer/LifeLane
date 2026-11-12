"""
notifier.py — Mock notification delivery for LifeLane dispatch events.

Provides in-memory notification logging for the Phase 2 POC.
In Phase 8 (FastAPI) this will be replaced by a real push notification
or WebSocket delivery mechanism.

Notification events follow the event taxonomy defined in the v2 spec.
"""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Event type constants
# ---------------------------------------------------------------------------

class NotificationEvent:
    """String constants for notification event types."""
    REQUEST_ACCEPTED = "REQUEST_ACCEPTED"
    AUTH_FAILURE = "AUTH_FAILURE"
    ROUTE_CHANGED = "ROUTE_CHANGED"
    JUNCTION_PREPARING = "JUNCTION_PREPARING"
    JUNCTION_SERVED = "JUNCTION_SERVED"
    HOSPITAL_ARRIVAL = "HOSPITAL_ARRIVAL"
    VERIFICATION_TIMEOUT = "VERIFICATION_TIMEOUT"
    UNVERIFIED_SIREN_ALERT = "UNVERIFIED_SIREN_ALERT"
    GPS_STALE = "GPS_STALE"
    REQUEST_EXPIRED = "REQUEST_EXPIRED"
    DUPLICATE_REQUEST = "DUPLICATE_REQUEST"
    GPS_DEVIATION = "GPS_DEVIATION"
    TEMP_VERIFICATION_FAILED = "TEMP_VERIFICATION_FAILED"
    TEMP_VERIFICATION_SUCCESS = "TEMP_VERIFICATION_SUCCESS"
    REQUEST_AUTHORIZED = "REQUEST_AUTHORIZED"
    PASSAGE_CONFIRMED = "PASSAGE_CONFIRMED"


@dataclass
class Notification:
    """A single notification record."""
    notification_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    ambulance_id: str = ""
    request_id: str = ""
    event_type: str = ""
    message: str = ""
    timestamp: float = field(default_factory=time.time)
    delivered: bool = False
    metadata: Dict = field(default_factory=dict)


class MockNotifier:
    """In-memory notification sink for the Phase 2 POC.

    In production this would push to an ambulance app, dispatch console, or
    WebSocket channel. Here it stores notifications in memory for inspection.
    """

    def __init__(self) -> None:
        self._notifications: List[Notification] = []

    def notify(
        self,
        ambulance_id: str,
        event_type: str,
        message: str,
        request_id: str = "",
        timestamp: Optional[float] = None,
        metadata: Optional[Dict] = None,
    ) -> Notification:
        """Record and return a notification.

        Args:
            ambulance_id: The ambulance this notification targets.
            event_type:   One of the NotificationEvent constants.
            message:      Human-readable description.
            request_id:   Associated request_id (if any).
            timestamp:    Override epoch time (defaults to now).
            metadata:     Optional dict of extra context.

        Returns:
            The created Notification object.
        """
        n = Notification(
            ambulance_id=ambulance_id,
            request_id=request_id,
            event_type=event_type,
            message=message,
            timestamp=timestamp if timestamp is not None else time.time(),
            delivered=True,  # Mock always delivers immediately
            metadata=metadata or {},
        )
        self._notifications.append(n)
        logger.info(
            "[notifier] %s → %s: %s", ambulance_id, event_type, message
        )
        return n

    def get_notifications(self, ambulance_id: str) -> List[Notification]:
        """Return all notifications for a given ambulance (chronological order)."""
        return [n for n in self._notifications if n.ambulance_id == ambulance_id]

    def get_by_event_type(self, event_type: str) -> List[Notification]:
        """Return all notifications of a given event type."""
        return [n for n in self._notifications if n.event_type == event_type]

    def get_all(self) -> List[Notification]:
        """Return all notifications."""
        return list(self._notifications)

    def clear(self) -> None:
        """Clear all stored notifications (useful for test teardown)."""
        self._notifications.clear()

    def __len__(self) -> int:
        return len(self._notifications)

