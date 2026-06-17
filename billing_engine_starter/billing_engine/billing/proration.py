"""
Proration — compute credits/charges when changing plans mid‑cycle.
"""

from datetime import date
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from billing_engine.money import Money
from billing_engine.taxes.base import TaxCalculator, TaxContext, TaxBreakdown


@dataclass
class ProrationResult:
    credit: Money
    charge: Money
    credit_tax: Money
    charge_tax: Money
    total: Money  # net effect (charge - credit)


def compute_proration(
    old_plan_price: Money,
    new_plan_price: Money,
    period_start: date,
    period_end: date,
    switch_date: date,
    tax_calc: TaxCalculator,
    tax_context: TaxContext,
) -> ProrationResult:
    """
    Compute prorated credit and charge when switching plans.
    The switch occurs on `switch_date`. The old plan is used up to that date,
    the new plan from that date onward.
    """
    # Validate inputs
    if not (period_start <= switch_date <= period_end):
        raise ValueError("switch_date must be within the billing period")
    if old_plan_price.currency != new_plan_price.currency:
        raise ValueError("old and new plan prices must have the same currency")

    total_days = (period_end - period_start).days
    if total_days <= 0:
        total_days = 1

    days_remaining = (period_end - switch_date).days

    # Prorate charges using Decimal ratio
    ratio = Decimal(days_remaining) / Decimal(total_days)
    credit = old_plan_price * ratio
    charge = new_plan_price * ratio

    # Apply tax to both legs
    tax_credit = tax_calc.apply(credit, tax_context).total
    tax_charge = tax_calc.apply(charge, tax_context).total

    net = charge - credit  # Money supports subtraction

    return ProrationResult(
        credit=credit,
        charge=charge,
        credit_tax=tax_credit,
        charge_tax=tax_charge,
        total=net,
    )
