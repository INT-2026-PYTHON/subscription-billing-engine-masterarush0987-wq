"""
FixedAmountDiscount — flat ₹500 off. Capped at subtotal.
"""

from billing_engine.money import Money
from billing_engine.discounts.base import Discount, DiscountContext


class FixedAmountDiscount(Discount):
    def __init__(self, amount: Money) -> None:
        if not isinstance(amount, Money):
            raise TypeError("amount must be Money")
        if amount.is_negative():
            raise ValueError("amount cannot be negative")
        self.amount = amount

    def apply(self, subtotal: Money, context: DiscountContext) -> Money:
        if not isinstance(subtotal, Money):
            raise TypeError("subtotal must be Money")
        if subtotal.is_negative():
            raise ValueError("subtotal cannot be negative")
        if not isinstance(context, DiscountContext):
            raise TypeError("context must be DiscountContext")

        if self.amount >= subtotal:
            return subtotal
        return self.amount
