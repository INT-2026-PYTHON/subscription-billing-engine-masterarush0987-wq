"""
Dunning — payment retry logic.
"""

from datetime import date, timedelta
from typing import Optional
from enum import Enum


# Retry delays in days: first retry after 1 day, second after 3 days, third after 7 days.
RETRY_DELAYS_DAYS = [1, 3, 7]
MAX_ATTEMPTS = 3  # maximum number of retry attempts before marking as failed


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
