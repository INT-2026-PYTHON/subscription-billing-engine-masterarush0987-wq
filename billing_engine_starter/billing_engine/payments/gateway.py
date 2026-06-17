"""
Payment gateway abstractions.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


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
