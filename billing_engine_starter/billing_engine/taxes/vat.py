"""
VATCalculator — single-rate VAT (e.g. 19% in Germany).
"""

from decimal import Decimal

from billing_engine.money import Money
from billing_engine.taxes.base import TaxCalculator, TaxContext, TaxBreakdown


class VATCalculator(TaxCalculator):
    def __init__(self, rate: Decimal) -> None:
        if not isinstance(rate, Decimal):
            raise TypeError("rate must be Decimal")
        if not (0 <= rate <= 1):
            raise ValueError("rate must be between 0 and 1")
        self.rate = rate

    def apply(self, taxable: Money, context: TaxContext) -> TaxBreakdown:
        if not isinstance(taxable, Money):
            raise TypeError("taxable must be Money")
        if taxable.is_negative():
            raise ValueError("taxable cannot be negative")
        if not isinstance(context, TaxContext):
            raise TypeError("context must be TaxContext")

        vat = taxable * self.rate
        # Format percentage nicely, e.g. "VAT 19.0%"
        percent = int(self.rate * 100) if self.rate == self.rate.quantize(Decimal("0.01")) else self.rate * 100
        # Simpler: just use the rate as a decimal string
        label = f"VAT {self.rate * 100}%"
        return TaxBreakdown(components=[(label, vat)], total=vat)
