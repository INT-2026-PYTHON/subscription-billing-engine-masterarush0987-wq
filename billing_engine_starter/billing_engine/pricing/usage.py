"""
UsageBased — pay per unit consumed.

Example: ₹0.50 per API call. 1200 calls => ₹600.
"""

from billing_engine.money import Money
from billing_engine.pricing.base import PricingStrategy


class UsageBased(PricingStrategy):
    def __init__(self, unit_price: Money) -> None:
        if not isinstance(unit_price, Money):
            raise TypeError("unit_price must be Money")
        if unit_price.is_negative():
            raise ValueError("unit_price cannot be negative")
        self.unit_price = unit_price

    def calculate(self, quantity: int) -> Money:
        if not isinstance(quantity, int):
            raise TypeError("quantity must be int")
        if quantity < 0:
            raise ValueError("quantity cannot be negative")
        return self.unit_price * quantity
