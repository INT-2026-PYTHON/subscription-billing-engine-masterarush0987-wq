"""
Freemium — first N units are free, overage delegated to another strategy.

Example: 1000 free API calls per month, then ₹0.50 per call (UsageBased).
"""

from billing_engine.money import Money
from billing_engine.pricing.base import PricingStrategy


class Freemium(PricingStrategy):
    """Returns 0 for quantity <= free_quota, else delegates overage to inner strategy."""

    def __init__(self, free_quota: int, overage_strategy: PricingStrategy) -> None:
        if not isinstance(free_quota, int):
            raise TypeError("free_quota must be int")
        if free_quota < 0:
            raise ValueError("free_quota cannot be negative")
        if not isinstance(overage_strategy, PricingStrategy):
            raise TypeError("overage_strategy must be a PricingStrategy")
        self.free_quota = free_quota
        self.overage_strategy = overage_strategy

    def calculate(self, quantity: int) -> Money:
        if not isinstance(quantity, int):
            raise TypeError("quantity must be int")
        if quantity < 0:
            raise ValueError("quantity cannot be negative")

        if quantity <= self.free_quota:
            # Return zero in the same currency as the overage strategy
            sample = self.overage_strategy.calculate(1)
            return Money(0, sample.currency)

        overage = quantity - self.free_quota
        return self.overage_strategy.calculate(overage)
