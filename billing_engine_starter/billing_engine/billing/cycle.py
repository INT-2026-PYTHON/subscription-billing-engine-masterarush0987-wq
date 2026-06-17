"""
BillingCycle — orchestrates billing for all due subscriptions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import calendar
import sqlite3
from typing import Optional, Callable

from billing_engine.db.database import Database
from billing_engine.db.repository import (
    CustomerRepository,
    PlanRepository,
    SubscriptionRepository,
    InvoiceRepository,
    InvoiceLineItemRepository,
    LedgerRepository,
    PaymentAttemptRepository,
    UsageRecordRepository,
)
from billing_engine.models import (
    SubscriptionStatus,
    InvoiceStatus,
    LedgerDirection,
    LedgerEntry,
    Invoice,
    Plan,
)
from billing_engine.billing.pipeline import build_invoice
from billing_engine.pricing import FlatRate
from billing_engine.money import Money
from billing_engine.payments.gateway import PaymentGateway, ScriptedGateway


def add_months(d: date, months: int = 1) -> date:
    year = d.year + (d.month + months - 1) // 12
    month = (d.month + months - 1) % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


@dataclass
class BillingResult:
    subscriptions_billed: int = 0
    invoices_created: int = 0
    invoices_skipped_duplicate: int = 0
    trials_activated: int = 0


class BillingCycle:
    def __init__(
        self,
        db: Database,
        customer_repo: CustomerRepository,
        plan_repo: PlanRepository,
        subscription_repo: SubscriptionRepository,
        usage_repo: UsageRecordRepository,
        invoice_repo: InvoiceRepository,
        line_item_repo: InvoiceLineItemRepository,
        ledger_repo: LedgerRepository,
        strategy_factory: Callable[[Plan], FlatRate],
        discount_factory: Callable,
        tax_factory: Callable,
        gateway: Optional[PaymentGateway] = None,
    ):
        self.db = db
        self.customer_repo = customer_repo
        self.plan_repo = plan_repo
        self.subscription_repo = subscription_repo
        self.usage_repo = usage_repo
        self.invoice_repo = invoice_repo
        self.line_item_repo = line_item_repo
        self.ledger_repo = ledger_repo
        self.strategy_factory = strategy_factory
        self.discount_factory = discount_factory
        self.tax_factory = tax_factory
        self.gateway = gateway or ScriptedGateway([])

    def run(self, as_of: date) -> BillingResult:
        result = BillingResult()

        all_subs = self.subscription_repo.list_all()

        for sub in all_subs:
            # Handle trial expiration
            if sub.status == SubscriptionStatus.TRIAL and sub.trial_end and sub.trial_end <= as_of:
                self.subscription_repo.update_status(sub.id, SubscriptionStatus.ACTIVE)
                result.trials_activated += 1
                # Re‑fetch subscription to get updated status
                sub = self.subscription_repo.get(sub.id)

            if sub.status != SubscriptionStatus.ACTIVE:
                continue

            # Check if due for billing
            if sub.current_period_end > as_of:
                continue

            plan = self.plan_repo.get(sub.plan_id)
            if not plan:
                continue

            customer = self.customer_repo.get(sub.customer_id)
            if not customer:
                continue

            usage_quantity = 0
            if plan.pricing_type.value in ("USAGE", "TIERED", "FREEMIUM"):
                usage_quantity = self.usage_repo.sum_for_period(
                    sub.id, "calls", sub.current_period_start, sub.current_period_end
                )

            strategy = self.strategy_factory(plan)
            discount = None
            tax_calc, tax_context = self.tax_factory(customer)

            invoice_count = self.invoice_repo.count_for_subscription(sub.id)

            invoice = build_invoice(
                subscription=sub,
                plan=plan,
                strategy=strategy,
                discount=discount,
                tax_calc=tax_calc,
                tax_context=tax_context,
                usage_quantity=usage_quantity,
                period_start=sub.current_period_start,
                period_end=sub.current_period_end,
                invoice_count_so_far=invoice_count,
            )

            # Try to save invoice; skip if duplicate
            try:
                saved = self.invoice_repo.add(invoice)
            except sqlite3.IntegrityError:
                result.invoices_skipped_duplicate += 1
                continue

            for li in saved.line_items:
                self.line_item_repo.add(li)

            # ledger debit
            entry = LedgerEntry(
                id=None,
                invoice_id=saved.id,
                customer_id=sub.customer_id,
                amount=saved.total,
                direction=LedgerDirection.DEBIT,
                reason=f"Invoice #{saved.id}",
                created_at=None,
            )
            self.ledger_repo.add(entry)

            # mark issued
            with self.db.connect() as conn:
                conn.execute("UPDATE invoices SET status = 'ISSUED' WHERE id = ?", (saved.id,))

            # advance period to next month (same day)
            new_start = sub.current_period_end
            new_end = add_months(new_start, 1)  # one month later
            self.subscription_repo.update_period(sub.id, new_start, new_end)

            result.subscriptions_billed += 1
            result.invoices_created += 1

        return result
