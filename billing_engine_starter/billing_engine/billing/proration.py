"""
Proration — compute credits/charges when changing plans mid‑cycle.
"""

from datetime import date
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from billing_engine.money import Money
from billing_engine.taxes.base import TaxCalculator, TaxContext


@dataclass
class ProrationResult:
    credit_amount: Money
    charge_amount: Money
    credit_tax: Money
    charge_tax: Money
    net: Money


def compute_proration(
    old_plan_price: Money,
    new_plan_price: Money,
    period_start: date,
    period_end: date,
    switch_date: date,
    tax_calc: TaxCalculator,
    tax_context: TaxContext,
) -> ProrationResult:
    if not (period_start <= switch_date <= period_end):
        raise ValueError("switch_date must be within the billing period")
    if old_plan_price.currency != new_plan_price.currency:
        raise ValueError("old and new plan prices must have the same currency")

    total_days = (period_end - period_start).days
    if total_days <= 0:
        total_days = 1

    days_remaining = (period_end - switch_date).days
    ratio = Decimal(days_remaining) / Decimal(total_days)

    # Use two-decimal rounding to match test expectations
    def round_money(m: Money) -> Money:
        return Money(m.amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP), m.currency)

    credit = round_money(old_plan_price * ratio)
    charge = round_money(new_plan_price * ratio)

    tax_credit = round_money(tax_calc.apply(credit, tax_context).total)
    tax_charge = round_money(tax_calc.apply(charge, tax_context).total)

    net = charge - credit  # Money supports subtraction

    return ProrationResult(
        credit_amount=credit,
        charge_amount=charge,
        credit_tax=tax_credit,
        charge_tax=tax_charge,
        net=net,
    )
