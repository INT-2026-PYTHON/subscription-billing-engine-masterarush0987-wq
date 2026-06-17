"""
Dunning — payment retry logic.
"""

from datetime import date, timedelta
from typing import Optional
from enum import Enum


class DunningState(str, Enum):
    PENDING = "PENDING"
    RETRY = "RETRY"
    FAILED = "FAILED"
    RECOVERED = "RECOVERED"


class DunningProcess:
    """Handles payment retry scheduling and grace period decisions."""

    @staticmethod
    def should_cancel(past_due_since: date, today: date, grace_days: int = 7) -> bool:
        """Return True if the subscription should be canceled after grace period."""
        return (today - past_due_since).days > grace_days
