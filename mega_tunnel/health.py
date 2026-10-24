"""Per-edge circuit breakers: no restarts and no global node eviction."""
from dataclasses import dataclass
from .models import EdgeState


@dataclass
class Circuit:
    state: EdgeState = EdgeState.HEALTHY
    consecutive_failures: int = 0
    recovery_successes: int = 0
    quarantine_until: float = 0.0
    # Measured monotonic seconds; caller should inject clock.
    cooldown_s: float = 60.0
    suspect_after: int = 2
    quarantine_after: int = 4
    restore_after: int = 3

    @property
    def admits_new_flows(self) -> bool:
        return self.state == EdgeState.HEALTHY

    def observe(self, success: bool, now: float, *, active_probe: bool = False) -> EdgeState:
        if self.state == EdgeState.QUARANTINED:
            if now < self.quarantine_until:
                return self.state
            # Only an active, verified probe can start recovery.
            if not active_probe:
                return self.state
            self.state = EdgeState.PROBATION
            self.recovery_successes = 0

        if self.state == EdgeState.PROBATION:
            if not active_probe or not success:
                if not success:
                    return self._quarantine(now)
                return self.state
            self.recovery_successes += 1
            if self.recovery_successes >= self.restore_after:
                self.state = EdgeState.HEALTHY
                self.consecutive_failures = 0
                self.recovery_successes = 0
            return self.state

        if success:
            self.consecutive_failures = 0
            if self.state == EdgeState.SUSPECT:
                # Require a verified active probe for restoring acceptance.
                if active_probe:
                    self.state = EdgeState.HEALTHY
            return self.state

        self.consecutive_failures += 1
        if self.consecutive_failures >= self.quarantine_after:
            return self._quarantine(now)
        if self.consecutive_failures >= self.suspect_after:
            self.state = EdgeState.SUSPECT
        return self.state

    def _quarantine(self, now: float) -> EdgeState:
        self.state = EdgeState.QUARANTINED
        self.quarantine_until = now + self.cooldown_s
        self.recovery_successes = 0
        return self.state
