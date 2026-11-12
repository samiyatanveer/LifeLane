"""
recovery.py — Bounded coordination recovery after ambulance passage.

After an ambulance passes through a junction, the normal coordinated
signal plan must be restored without:
  - Resetting blindly to phase zero.
  - Causing indefinite starvation of delayed movements.
  - Exceeding configured maximum recovery durations.

Phase 1: mock implementation tracking timing recovery and queue recovery
separately, as required by the specification.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

from lifelane_engine import config

logger = logging.getLogger(__name__)


class RecoveryPhase(Enum):
    """Sub-phases within the RECOVERING controller state."""
    SERVE_DELAYED = auto()   # Serve movements that were held during priority
    TIMING_RECOVERY = auto() # Re-align signal offsets / phase timing
    QUEUE_RECOVERY = auto()  # Wait for downstream queues to dissipate
    COMPLETE = auto()


@dataclass
class RecoveryManager:
    """Manages the bounded recovery sequence for one junction.

    Tracks timing recovery and queue recovery durations separately,
    and enforces maximum bounds to prevent traffic starvation.
    """

    junction_id: str

    # Configuration
    max_delay_service_s: float = field(init=False)
    max_recovery_s: float = field(init=False)

    # Internal state
    phase: RecoveryPhase = field(default=RecoveryPhase.SERVE_DELAYED, init=False)
    recovery_started_at: Optional[float] = field(default=None, init=False)
    timing_recovery_start: Optional[float] = field(default=None, init=False)
    timing_recovery_end: Optional[float] = field(default=None, init=False)
    queue_recovery_start: Optional[float] = field(default=None, init=False)
    queue_recovery_end: Optional[float] = field(default=None, init=False)
    delay_service_started: Optional[float] = field(default=None, init=False)

    def __post_init__(self) -> None:
        rec_cfg = config.get("recovery")
        self.max_delay_service_s = float(rec_cfg.get("max_delay_service_s", 60.0))
        self.max_recovery_s = float(rec_cfg.get("max_recovery_duration_s", 120.0))

    def start(self, now: float | None = None) -> None:
        """Begin the recovery sequence."""
        if now is None:
            now = time.time()
        self.recovery_started_at = now
        self.delay_service_started = now
        self.phase = RecoveryPhase.SERVE_DELAYED
        logger.info(
            "[recovery] junction=%s: recovery started — serving delayed movements",
            self.junction_id,
        )

    def tick(self, now: float | None = None, queue_cleared: bool = False) -> RecoveryPhase:
        """Advance the recovery state machine on each time step.

        Args:
            now:           Current time (seconds).
            queue_cleared: True if downstream queue occupancy is acceptable.

        Returns:
            The current RecoveryPhase.
        """
        if now is None:
            now = time.time()

        if self.recovery_started_at is None:
            raise RuntimeError(f"RecoveryManager.start() must be called before tick() on {self.junction_id}")

        elapsed = now - self.recovery_started_at

        # Safety bound — never exceed maximum total recovery time
        if elapsed >= self.max_recovery_s:
            logger.warning(
                "[recovery] junction=%s: maximum recovery duration reached (%.0fs) — forcing COMPLETE",
                self.junction_id, self.max_recovery_s,
            )
            self._complete(now)
            return self.phase

        if self.phase == RecoveryPhase.SERVE_DELAYED:
            delay_elapsed = now - (self.delay_service_started if self.delay_service_started is not None else now)
            if delay_elapsed >= self.max_delay_service_s:
                logger.info(
                    "[recovery] junction=%s: delay service complete (%.0fs) → timing recovery",
                    self.junction_id, delay_elapsed,
                )
                self.phase = RecoveryPhase.TIMING_RECOVERY
                self.timing_recovery_start = now

        elif self.phase == RecoveryPhase.TIMING_RECOVERY:
            # In Phase 1 (mock): timing recovery is instantaneous.
            # Phase 3 will use the shared simulation clock for offset re-alignment.
            if self.timing_recovery_end is None:
                self.timing_recovery_end = now
                logger.info(
                    "[recovery] junction=%s: timing recovery complete → queue recovery",
                    self.junction_id,
                )
                self.phase = RecoveryPhase.QUEUE_RECOVERY
                self.queue_recovery_start = now

        elif self.phase == RecoveryPhase.QUEUE_RECOVERY:
            if queue_cleared:
                self.queue_recovery_end = now
                logger.info(
                    "[recovery] junction=%s: queue recovery complete → COMPLETE",
                    self.junction_id,
                )
                self._complete(now)

        return self.phase

    def _complete(self, now: float) -> None:
        if self.queue_recovery_end is None:
            self.queue_recovery_end = now
        self.phase = RecoveryPhase.COMPLETE

    def is_complete(self) -> bool:
        """Return True when recovery is finished."""
        return self.phase == RecoveryPhase.COMPLETE

    def summary(self) -> dict:
        """Return a dict with recovery duration metrics."""
        timing_dur: float = 0.0
        if self.timing_recovery_start and self.timing_recovery_end:
            timing_dur = self.timing_recovery_end - self.timing_recovery_start

        queue_dur: float = 0.0
        if self.queue_recovery_start and self.queue_recovery_end:
            queue_dur = self.queue_recovery_end - self.queue_recovery_start

        total_dur: float = 0.0
        if self.recovery_started_at and self.queue_recovery_end:
            total_dur = self.queue_recovery_end - self.recovery_started_at

        return {
            "junction_id": self.junction_id,
            "timing_recovery_duration_s": round(timing_dur, 2),
            "queue_recovery_duration_s": round(queue_dur, 2),
            "total_recovery_duration_s": round(total_dur, 2),
        }
