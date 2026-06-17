"""
PercentageDiscount — 20% off, etc. Capped at subtotal.
"""

from decimal import Decimal

from billing_engine.money import Money
from billing_engine.discounts.base import Discount, DiscountContext


class PercentageDiscount(Discount):
    def __init__(self, percentage: Decimal) -> None:
        if not isinstance(percentage, Decimal):
            raise TypeError("percentage must be Decimal")
        if percentage < Decimal("0") or percentage > Decimal("1"):
            raise ValueError("percentage must be between 0 and 1 (inclusive)")
        self.percentage = percentage

    def apply(self, subtotal: Money, context: DiscountContext) -> Money:
        if not isinstance(subtotal, Money):
            raise TypeError("subtotal must be Money")
        if subtotal.is_negative():
            raise ValueError("subtotal cannot be negative")
        if not isinstance(context, DiscountContext):
            raise TypeError("context must be DiscountContext")

        discount = subtotal * self.percentage
        if discount >= subtotal:
            return subtotal
        return discount
