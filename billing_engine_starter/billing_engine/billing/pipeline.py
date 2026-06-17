"""
build_invoice — PURE function that turns inputs into an Invoice dataclass.

⚠️ NO database calls here. No `datetime.now()`. No PDF. Just math.

The order is FIXED:
    1. base       = strategy.calculate(usage)
    2. discount   = discount.apply(base) if discount else 0
    3. taxable    = base - discount
    4. tax        = tax_calc.apply(taxable)
    5. total      = taxable + tax.total
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
    # Input validation
    if subscription.id is None:
        raise ValueError("subscription must have an id")
    if plan.currency != strategy.calculate(0).currency:
        raise ValueError("Strategy currency does not match plan currency")

    currency = plan.currency

    # 1. Base charge
    base = strategy.calculate(usage_quantity)
    if base.currency != currency:
        raise ValueError("Base amount currency mismatch")

    # 2. Discount
    if discount is not None:
        ctx = DiscountContext(invoice_count_so_far=invoice_count_so_far)
        discount_amount = discount.apply(base, ctx)
        if discount_amount.currency != currency:
            raise ValueError("Discount amount currency mismatch")
    else:
        discount_amount = Money(0, currency)

    # 3. Taxable amount (base - discount, never negative)
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

    # Build the Invoice dataclass (no 'currency' argument – it's derived from Money objects)
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
    )
