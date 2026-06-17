"""
Payment gateway abstractions.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import random


@dataclass
class PaymentResult:
    success: bool
    failure_reason: Optional[str] = None


class PaymentGateway(ABC):
    @abstractmethod
    def charge(self, invoice_id: int, amount_cents: int, currency: str) -> PaymentResult:
        raise NotImplementedError


class ScriptedGateway(PaymentGateway):
    """Gateway that returns pre‑scripted results in order."""

    def __init__(self, results: list[PaymentResult]) -> None:
        self.results = results
        self._idx = 0

    def charge(self, invoice_id: int, amount_cents: int, currency: str) -> PaymentResult:
        result = self.results[self._idx]
        self._idx += 1
        return result


class FakeRandomGateway(PaymentGateway):
    """Fake gateway that randomly succeeds or fails (for testing)."""

    def __init__(self, success_rate: float = 0.8) -> None:
        self.success_rate = success_rate

    def charge(self, invoice_id: int, amount_cents: int, currency: str) -> PaymentResult:
        if random.random() < self.success_rate:
            return PaymentResult(True)
        return PaymentResult(False, "RANDOM_FAILURE")
