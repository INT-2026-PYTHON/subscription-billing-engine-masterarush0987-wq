"""
FirstMonthFree — 100% off the very first invoice, 0% after.
"""

from billing_engine.money import Money
from billing_engine.discounts.base import Discount, DiscountContext


class FirstMonthFree(Discount):
    def apply(self, subtotal: Money, context: DiscountContext) -> Money:
        if not isinstance(subtotal, Money):
            raise TypeError("subtotal must be Money")
        if subtotal.is_negative():
            raise ValueError("subtotal cannot be negative")
        if not isinstance(context, DiscountContext):
            raise TypeError("context must be DiscountContext")

        if context.invoice_count_so_far == 0:
            return subtotal  # 100% off
        return Money(0, subtotal.currency)
