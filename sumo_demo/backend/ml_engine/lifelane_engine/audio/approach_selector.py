"""
approach_selector.py — Per-approach audio siren evidence accumulator.

SAFETY RULE:  This module only accumulates evidence.
              It NEVER directly causes a signal to turn green.
              A CONFIRMED state here is ONE prerequisite among several.

The approach selector:
  1. Receives a siren probability (0.0–1.0) for each approach each window.
  2. Smooths evidence using a short running mean.
  3. Requires N consecutive positive windows from the same approach.
  4. Enforces a cooldown period and an activation-rate limit.
  5. Flags conflicts when multiple approaches claim siren simultaneously.
"""
from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Deque, Dict, List, Optional

from lifelane_engine import config

logger = logging.getLogger(__name__)

APPROACHES: tuple[str, ...] = ("north", "east", "south", "west")


class ApproachState(Enum):
    """Evidence state for a single approach."""
    IDLE = auto()
    SUSPECTED = auto()   # 1–2 consecutive positive windows
    CONFIRMED = auto()   # ≥ N consecutive positive windows
    COOLDOWN = auto()    # recently served; rejecting new activations temporarily


@dataclass
class ApproachEvidence:
    """Tracks sliding-window evidence and state for one approach."""

    approach: str
    threshold: float = 0.5
    required_windows: int = 3
    cooldown_s: float = 30.0
    max_activations_per_hour: int = 4

    # Internal state
    state: ApproachState = field(default=ApproachState.IDLE, init=False)
    consecutive_positive: int = field(default=0, init=False)
    recent_scores: Deque[float] = field(default_factory=lambda: deque(maxlen=5), init=False)
    last_activation_times: List[float] = field(default_factory=list, init=False)
    cooldown_until: float = field(default=0.0, init=False)

    def update(self, score: float, now: float | None = None) -> ApproachState:
        """Process one audio-window score and return the new state.

        Args:
            score: Siren probability [0.0, 1.0] for this window.
            now:   Current wall/sim time (seconds). Defaults to time.time().

        Returns:
            The updated ApproachState.
        """
        if now is None:
            now = time.time()

        self.recent_scores.append(score)
        smoothed = sum(self.recent_scores) / len(self.recent_scores)

        # Exit cooldown if time has elapsed
        if self.state == ApproachState.COOLDOWN and now >= self.cooldown_until:
            logger.debug("[approach_selector] %s: cooldown ended", self.approach)
            self.state = ApproachState.IDLE
            self.consecutive_positive = 0

        if self.state == ApproachState.COOLDOWN:
            # Still in cooldown; ignore new evidence
            return self.state

        # Rate limit check
        cutoff = now - 3600.0
        self.last_activation_times = [t for t in self.last_activation_times if t > cutoff]
        if len(self.last_activation_times) >= self.max_activations_per_hour:
            logger.warning(
                "[approach_selector] %s: activation-rate limit reached (%d/hr)",
                self.approach, self.max_activations_per_hour,
            )
            return self.state

        # A window is positive only if the CURRENT raw score exceeds the threshold.
        # Smoothed scores are used for confidence logging but the streak is reset
        # by any individual below-threshold window (prevents a single dip from
        # keeping a stale confirmation alive via prior positive history).
        positive = score >= self.threshold

        if positive:
            self.consecutive_positive += 1
            logger.debug(
                "[approach_selector] %s: positive window %d/%d (smoothed=%.3f)",
                self.approach, self.consecutive_positive, self.required_windows, smoothed,
            )
            if self.consecutive_positive >= self.required_windows:
                if self.state != ApproachState.CONFIRMED:
                    logger.info(
                        "[approach_selector] %s: CONFIRMED after %d consecutive windows",
                        self.approach, self.consecutive_positive,
                    )
                    self.last_activation_times.append(now)
                self.state = ApproachState.CONFIRMED
            else:
                self.state = ApproachState.SUSPECTED
        else:
            if self.consecutive_positive > 0:
                logger.debug(
                    "[approach_selector] %s: negative window resets streak (was %d)",
                    self.approach, self.consecutive_positive,
                )
            self.consecutive_positive = 0
            self.state = ApproachState.IDLE

        return self.state

    def enter_cooldown(self, now: float | None = None) -> None:
        """Start the cooldown period after a successful service."""
        if now is None:
            now = time.time()
        self.cooldown_until = now + self.cooldown_s
        self.state = ApproachState.COOLDOWN
        self.consecutive_positive = 0
        logger.info(
            "[approach_selector] %s: entering cooldown until +%.0fs",
            self.approach, self.cooldown_s,
        )

    def reset(self) -> None:
        """Hard-reset to IDLE (e.g. on request expiry or arbitration clear)."""
        self.state = ApproachState.IDLE
        self.consecutive_positive = 0
        self.recent_scores.clear()


class ApproachSelector:
    """Manages siren evidence across all four approaches for one junction.

    SAFETY:
      - Returns at most one confirmed approach at a time.
      - If multiple approaches are simultaneously confirmed, declares a CONFLICT.
        The safety controller must handle conflicts; this selector never resolves
        a conflict by silently picking a winner.
    """

    CONFLICT = "CONFLICT"

    def __init__(self, junction_id: str) -> None:
        cfg = config.get("approach_selector")
        required_windows: int = cfg.get("confirmation_windows", 3)
        cooldown_s: float = float(cfg.get("cooldown_s", 30))
        max_rate: int = int(cfg.get("max_activations_per_hour", 4))

        self.junction_id = junction_id
        self._evidences: Dict[str, ApproachEvidence] = {
            ap: ApproachEvidence(
                approach=ap,
                required_windows=required_windows,
                cooldown_s=cooldown_s,
                max_activations_per_hour=max_rate,
            )
            for ap in APPROACHES
        }

    def update(
        self,
        scores: Dict[str, float],
        now: float | None = None,
    ) -> Optional[str]:
        """Process one round of per-approach siren scores.

        Args:
            scores: Mapping of approach → siren probability [0, 1].
                    Missing approaches default to 0.0.
            now:    Current time (seconds). Defaults to time.time().

        Returns:
            - The confirmed approach name if exactly one is confirmed.
            - ApproachSelector.CONFLICT if multiple approaches are confirmed.
            - None if no approach is confirmed.
        """
        if now is None:
            now = time.time()

        confirmed = []
        for ap in APPROACHES:
            score = scores.get(ap, 0.0)
            state = self._evidences[ap].update(score, now=now)
            if state == ApproachState.CONFIRMED:
                confirmed.append(ap)

        if len(confirmed) > 1:
            logger.warning(
                "[approach_selector] junction=%s CONFLICT: multiple approaches confirmed: %s",
                self.junction_id, confirmed,
            )
            return self.CONFLICT

        if len(confirmed) == 1:
            logger.info(
                "[approach_selector] junction=%s confirmed approach: %s",
                self.junction_id, confirmed[0],
            )
            return confirmed[0]

        return None

    def get_state(self, approach: str) -> ApproachState:
        """Return the current evidence state for a specific approach."""
        return self._evidences[approach].state

    def enter_cooldown(self, approach: str, now: float | None = None) -> None:
        """Put an approach into cooldown after service."""
        self._evidences[approach].enter_cooldown(now=now)

    def reset_approach(self, approach: str) -> None:
        """Hard-reset a specific approach."""
        self._evidences[approach].reset()

    def reset_all(self) -> None:
        """Hard-reset all approaches."""
        for ev in self._evidences.values():
            ev.reset()
