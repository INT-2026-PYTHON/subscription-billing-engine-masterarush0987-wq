"""
NoTax — for jurisdictions where you don't charge tax (or the customer is tax-exempt).
"""

from billing_engine.money import Money
from billing_engine.taxes.base import TaxCalculator, TaxContext, TaxBreakdown


class NoTax(TaxCalculator):
    def apply(self, taxable: Money, context: TaxContext) -> TaxBreakdown:
        if not isinstance(taxable, Money):
            raise TypeError("taxable must be Money")
        if taxable.is_negative():
            raise ValueError("taxable cannot be negative")
        if not isinstance(context, TaxContext):
            raise TypeError("context must be TaxContext")

        # No tax → components empty, total = 0 in the same currency
        zero = Money(0, taxable.currency)
        return TaxBreakdown(components=[], total=zero)
