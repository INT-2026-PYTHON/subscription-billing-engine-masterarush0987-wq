"""
GSTCalculator — Indian Goods & Services Tax.

The rule:
    - If customer_state == seller_state (or seller_state is "")  =>  intra-state
        -> charge CGST + SGST (split equally, e.g. 9% + 9% = 18%)
    - Else  =>  inter-state
        -> charge IGST (e.g. 18%)

Customers without a state code default to IGST (safe choice).
"""

from decimal import Decimal

from billing_engine.money import Money
from billing_engine.taxes.base import TaxCalculator, TaxContext, TaxBreakdown


class GSTCalculator(TaxCalculator):
    def __init__(self, cgst: Decimal, sgst: Decimal, igst: Decimal) -> None:
        if not isinstance(cgst, Decimal):
            raise TypeError("cgst must be Decimal")
        if not isinstance(sgst, Decimal):
            raise TypeError("sgst must be Decimal")
        if not isinstance(igst, Decimal):
            raise TypeError("igst must be Decimal")
        if not (0 <= cgst <= 1):
            raise ValueError("cgst must be between 0 and 1")
        if not (0 <= sgst <= 1):
            raise ValueError("sgst must be between 0 and 1")
        if not (0 <= igst <= 1):
            raise ValueError("igst must be between 0 and 1")
        # Sanity check: cgst + sgst should equal igst (within tolerance)
        if abs((cgst + sgst) - igst) > Decimal("0.0001"):
            raise ValueError("cgst + sgst must equal igst")
        self.cgst = cgst
        self.sgst = sgst
        self.igst = igst

    def apply(self, taxable: Money, context: TaxContext) -> TaxBreakdown:
        if not isinstance(taxable, Money):
            raise TypeError("taxable must be Money")
        if taxable.is_negative():
            raise ValueError("taxable cannot be negative")
        if not isinstance(context, TaxContext):
            raise TypeError("context must be TaxContext")

        # Determine intra vs inter
        is_intra = (context.customer_state and context.customer_state == context.seller_state)

        if is_intra:
            cgst_amount = taxable * self.cgst
            sgst_amount = taxable * self.sgst
            components = [("CGST", cgst_amount), ("SGST", sgst_amount)]
            total = cgst_amount + sgst_amount
        else:
            igst_amount = taxable * self.igst
            components = [("IGST", igst_amount)]
            total = igst_amount

        return TaxBreakdown(components=components, total=total)
