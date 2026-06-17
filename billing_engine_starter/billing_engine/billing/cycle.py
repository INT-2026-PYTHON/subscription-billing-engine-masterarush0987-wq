"""
BillingCycle — orchestrates billing for all due subscriptions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
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
        subs = self.subscription_repo.get_due_for_billing(as_of)
        result = BillingResult()

        for sub in subs:
            # Handle trial expiration
            if sub.status == SubscriptionStatus.TRIAL and sub.trial_end and sub.trial_end <= as_of:
                self.subscription_repo.update_status(sub.id, SubscriptionStatus.ACTIVE)
                sub.status = SubscriptionStatus.ACTIVE
                result.trials_activated += 1

            if sub.status != SubscriptionStatus.ACTIVE:
                continue

            plan = self.plan_repo.get(sub.plan_id)
            if not plan:
                continue

            customer = self.customer_repo.get(sub.customer_id)
            if not customer:
                continue

            # usage quantity (simplified)
            usage_quantity = 0
            if plan.pricing_type.value in ("USAGE", "TIERED", "FREEMIUM"):
                usage_quantity = self.usage_repo.sum_for_period(
                    sub.id, "calls", sub.current_period_start, sub.current_period_end
                )

            strategy = self.strategy_factory(plan)
            discount = None  # simplify for now
            tax_calc = self.tax_factory(customer)   # <-- pass customer here
            tax_context = self.tax_factory(customer) # but we need context; we'll use a simple one

            # Actually we need a TaxContext; we'll build one from customer.
            from billing_engine.taxes.base import TaxContext
            tax_context = TaxContext(
                customer_country=customer.country_code,
                customer_state=customer.state_code or "",
                seller_state="MH",
            )

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

            saved = self.invoice_repo.add(invoice)
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

            # advance period
            new_start = sub.current_period_end
            new_end = new_start + timedelta(days=30)
            self.subscription_repo.update_period(sub.id, new_start, new_end)

            result.subscriptions_billed += 1
            result.invoices_created += 1

        return result
