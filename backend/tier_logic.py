
"""
CANARY reporting-tier management.

Tier 1: 600-second reporting interval
Tier 2: 10-second reporting interval
Tier 3: 1-second reporting interval
"""

import time
from typing import Optional

try:
    from backend.config import REPORTING_INTERVALS, DEFAULT_TIER
except ImportError:
    REPORTING_INTERVALS = {1: 600, 2: 10, 3: 1}
    DEFAULT_TIER = 1


class TierManager:
    """Manages reporting tiers and alert-driven escalation."""

    def __init__(
        self,
        reporting_intervals: Optional[dict] = None,
        default_tier: int = DEFAULT_TIER,
        recovery_delay_seconds: float = 10.0,
    ):
        self.reporting_intervals = (
            reporting_intervals or REPORTING_INTERVALS
        )

        if default_tier not in self.reporting_intervals:
            raise ValueError(f"Invalid default tier: {default_tier}")

        if recovery_delay_seconds < 0:
            raise ValueError("Recovery delay cannot be negative.")

        self.default_tier = default_tier
        self.current_tier = default_tier
        self.recovery_delay_seconds = recovery_delay_seconds
        self.active_alerts = {}
        self._no_alerts_since = None
        self.last_transition = None

    @property
    def reporting_interval_seconds(self) -> int:
        return self.reporting_intervals[self.current_tier]

    def get_reporting_interval(self) -> int:
        return self.reporting_interval_seconds

    def get_status(self) -> dict:
        return {
            "current_tier": self.current_tier,
            "reporting_interval_seconds": self.reporting_interval_seconds,
            "active_alerts": dict(self.active_alerts),
            "alert_count": len(self.active_alerts),
            "recovery_pending": self._no_alerts_since is not None,
        }

    def set_alert(
        self,
        alert_name: str,
        active: bool = True,
        required_tier: int = 3,
    ) -> int:
        """Activate or clear an alert."""
        if not alert_name or not isinstance(alert_name, str):
            raise ValueError("alert_name must be a non-empty string.")

        if required_tier not in self.reporting_intervals:
            raise ValueError(f"Invalid required tier: {required_tier}")

        if active:
            self.active_alerts[alert_name] = required_tier
            self._no_alerts_since = None
        else:
            self.active_alerts.pop(alert_name, None)

            if not self.active_alerts:
                self._no_alerts_since = time.monotonic()

        self._update_tier()
        return self.current_tier

    def clear_all_alerts(self) -> int:
        """Clear alerts and begin the recovery delay."""
        self.active_alerts.clear()
        self._no_alerts_since = time.monotonic()
        self._update_tier()
        return self.current_tier

    def request_tier(self, tier: int) -> int:
        """Manually request a tier, unless an alert requires a higher one."""
        if tier not in self.reporting_intervals:
            raise ValueError(f"Invalid tier: {tier}")

        self.default_tier = tier

        if self.active_alerts:
            self._update_tier()
        else:
            self._change_tier(tier)
            self._no_alerts_since = None

        return self.current_tier

    def update(self, current_time: Optional[float] = None) -> int:
        """Reevaluate the tier, including recovery-delay expiration."""
        self._update_tier(current_time=current_time)
        return self.current_tier

    def _update_tier(self, current_time: Optional[float] = None):
        """Apply alert escalation and delayed recovery."""
        now = time.monotonic() if current_time is None else current_time

        if self.active_alerts:
            target_tier = max(
                self.default_tier,
                max(self.active_alerts.values()),
            )
            self._no_alerts_since = None
        else:
            if self._no_alerts_since is None:
                self._no_alerts_since = now

            elapsed = now - self._no_alerts_since

            if elapsed >= self.recovery_delay_seconds:
                target_tier = self.default_tier
            else:
                target_tier = self.current_tier

        self._change_tier(target_tier, now)

    def _change_tier(self, tier: int, timestamp=None):
        """Change tiers and record the transition."""
        if tier == self.current_tier:
            return

        previous_tier = self.current_tier
        self.current_tier = tier

        self.last_transition = {
            "from_tier": previous_tier,
            "to_tier": tier,
            "timestamp": (
                time.monotonic() if timestamp is None else timestamp
            ),
        }

    def reset(self):
        """Reset to the configured default tier."""
        self.active_alerts.clear()
        self.current_tier = self.default_tier
        self._no_alerts_since = None
        self.last_transition = None
