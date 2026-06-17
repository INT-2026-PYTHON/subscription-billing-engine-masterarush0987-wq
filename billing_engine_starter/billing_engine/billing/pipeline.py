"""
build_invoice — PURE function that turns inputs into an Invoice dataclass.

⚠️ NO database calls here. No `datetime.now()`. No PDF. Just math.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from billing_engine.money import Money
from billing_engine.models import (
    Invoice, InvoiceStatus, InvoiceLineItem, LineItemKind, Subscription, Plan,
)
from billing_engine.pricing.base import PricingStrategy
from billing_engine.discounts.base import Discount, DiscountContext
from billing_engine.taxes.base import TaxCalculator, TaxContext


def build_invoice(
    subscription: Subscription,
    plan: Plan,
    strategy: PricingStrategy,
    discount: Optional[Discount],
    tax_calc: TaxCalculator,
    tax_context: TaxContext,
    usage_quantity: int,
    period_start: date,
    period_end: date,
    invoice_count_so_far: int,
) -> Invoice:
    """Pure function. Returns an Invoice (id=None, status=DRAFT) ready to be persisted."""
    if subscription.id is None:
        raise ValueError("subscription must have an id")

    # 1. Base charge (strategy decides the currency)
    base = strategy.calculate(usage_quantity)
    currency = base.currency

    # 2. Discount
    if discount is not None:
        ctx = DiscountContext(invoice_count_so_far=invoice_count_so_far)
        discount_amount = discount.apply(base, ctx)
        if discount_amount.currency != currency:
            raise ValueError("Discount amount currency mismatch")
    else:
        discount_amount = Money(0, currency)

    # 3. Taxable amount
    taxable = base - discount_amount
    if taxable.is_negative():
        taxable = Money(0, currency)

    # 4. Tax
    tax_breakdown = tax_calc.apply(taxable, tax_context)
    tax_total = tax_breakdown.total
    if tax_total.currency != currency:
        raise ValueError("Tax total currency mismatch")

    # 5. Total
    total = taxable + tax_total

    # 6. Build line items
    line_items = []

    # BASE
    line_items.append(InvoiceLineItem(
        id=None,
        invoice_id=None,
        description=f"{plan.name} subscription",
        amount=base,
        kind=LineItemKind.BASE,
    ))

    # DISCOUNT (negative)
    if discount_amount.amount > 0:
        line_items.append(InvoiceLineItem(
            id=None,
            invoice_id=None,
            description="Discount applied",
            amount=Money(-discount_amount.amount, discount_amount.currency),
            kind=LineItemKind.DISCOUNT,
        ))

    # TAX components
    for label, tax_amount in tax_breakdown.components:
        if tax_amount.amount > 0:
            line_items.append(InvoiceLineItem(
                id=None,
                invoice_id=None,
                description=label,
                amount=tax_amount,
                kind=LineItemKind.TAX,
            ))

    return Invoice(
        id=None,
        subscription_id=subscription.id,
        period_start=period_start,
        period_end=period_end,
        subtotal=base,
        discount_total=discount_amount,
        tax_total=tax_total,
        total=total,
        status=InvoiceStatus.DRAFT,
        issued_at=None,
        pdf_path=None,
        line_items=line_items,
    )
