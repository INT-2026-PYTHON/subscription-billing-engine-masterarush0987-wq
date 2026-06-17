"""
Repositories — the ONLY place SQL lives.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
import json

from billing_engine.db.database import Database
from billing_engine.money import Money
from billing_engine.models import (
    Customer,
    Plan, PricingType, BillingPeriod,
    Subscription, SubscriptionStatus,
    Invoice, InvoiceStatus, InvoiceLineItem, LineItemKind,
    LedgerEntry, LedgerDirection,
)


# ============================================================
# CUSTOMERS
# ============================================================
class CustomerRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def add(self, customer: Customer) -> Customer:
        if customer.id is not None:
            raise ValueError("customer already has an id")
        with self.db.connect() as conn:
            cur = conn.execute(
                "INSERT INTO customers (name, email, country_code, state_code) VALUES (?, ?, ?, ?)",
                (customer.name, customer.email, customer.country_code, customer.state_code)
            )
            customer_id = cur.lastrowid
        return Customer(
            id=customer_id,
            name=customer.name,
            email=customer.email,
            country_code=customer.country_code,
            state_code=customer.state_code,
            created_at=customer.created_at,
        )

    def get(self, customer_id: int) -> Optional[Customer]:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT id, name, email, country_code, state_code, created_at FROM customers WHERE id = ?",
                (customer_id,)
            ).fetchone()
        if row is None:
            return None
        return Customer(id=row[0], name=row[1], email=row[2], country_code=row[3],
                        state_code=row[4], created_at=row[5])

    def find_by_email(self, email: str) -> Optional[Customer]:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT id, name, email, country_code, state_code, created_at FROM customers WHERE email = ?",
                (email,)
            ).fetchone()
        if row is None:
            return None
        return Customer(id=row[0], name=row[1], email=row[2], country_code=row[3],
                        state_code=row[4], created_at=row[5])

    def list_all(self) -> list[Customer]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT id, name, email, country_code, state_code, created_at FROM customers ORDER BY id"
            ).fetchall()
        return [
            Customer(id=r[0], name=r[1], email=r[2], country_code=r[3],
                     state_code=r[4], created_at=r[5])
            for r in rows
        ]


# ============================================================
# PLANS  +  PLAN TIERS
# ============================================================
class PlanRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def add(self, plan: Plan) -> Plan:
        if plan.id is not None:
            raise ValueError("plan already has an id")
        config_json = json.dumps(plan.config) if hasattr(plan, 'config') and plan.config else "{}"
        with self.db.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO plans (name, pricing_type, billing_period, currency, config_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (plan.name, plan.pricing_type.value, plan.billing_period.value, plan.currency, config_json)
            )
            plan_id = cur.lastrowid
        return Plan(
            id=plan_id,
            name=plan.name,
            pricing_type=plan.pricing_type,
            billing_period=plan.billing_period,
            currency=plan.currency,
            config=plan.config if hasattr(plan, 'config') else {}
        )

    def get(self, plan_id: int) -> Optional[Plan]:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT id, name, pricing_type, billing_period, currency, config_json FROM plans WHERE id = ?",
                (plan_id,)
            ).fetchone()
        if row is None:
            return None
        return Plan(
            id=row[0],
            name=row[1],
            pricing_type=PricingType(row[2]),
            billing_period=BillingPeriod(row[3]),
            currency=row[4],
            config=json.loads(row[5]) if row[5] else {}
        )

    def list_all(self) -> list[Plan]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT id, name, pricing_type, billing_period, currency, config_json FROM plans ORDER BY id"
            ).fetchall()
        return [
            Plan(
                id=r[0], name=r[1],
                pricing_type=PricingType(r[2]),
                billing_period=BillingPeriod(r[3]),
                currency=r[4],
                config=json.loads(r[5]) if r[5] else {}
            )
            for r in rows
        ]


class PlanTierRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def add(self, plan_id: int, from_units: int, to_units: Optional[int], unit_price: Money) -> int:
        with self.db.connect() as conn:
            cur = conn.execute(
                "INSERT INTO plan_tiers (plan_id, from_units, to_units, unit_price) VALUES (?, ?, ?, ?)",
                (plan_id, from_units, to_units, unit_price.to_storage())
            )
            return cur.lastrowid

    def list_for_plan(self, plan_id: int, currency: str) -> list[tuple[int, Optional[int], Money]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT from_units, to_units, unit_price FROM plan_tiers WHERE plan_id = ? ORDER BY from_units",
                (plan_id,)
            ).fetchall()
        return [
            (r[0], r[1], Money.from_storage(r[2], currency))
            for r in rows
        ]


# ============================================================
# DISCOUNTS
# ============================================================
class DiscountRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def add(self, code: str, discount_type: str, value: str, currency: Optional[str] = None) -> int:
        with self.db.connect() as conn:
            cur = conn.execute(
                "INSERT INTO discounts (code, discount_type, value, currency) VALUES (?, ?, ?, ?)",
                (code, discount_type, value, currency)
            )
            return cur.lastrowid

    def get_by_code(self, code: str) -> Optional[dict]:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT id, code, discount_type, value, currency, valid_until FROM discounts WHERE code = ?",
                (code,)
            ).fetchone()
        if row is None:
            return None
        return {
            "id": row[0],
            "code": row[1],
            "discount_type": row[2],
            "value": row[3],
            "currency": row[4],
            "valid_until": row[5],
        }


# ============================================================
# SUBSCRIPTIONS
# ============================================================
class SubscriptionRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def add(self, subscription: Subscription) -> Subscription:
        if subscription.id is not None:
            raise ValueError("subscription already has an id")
        with self.db.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO subscriptions (
                    customer_id, plan_id, status,
                    current_period_start, current_period_end,
                    trial_end, discount_id, past_due_since
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    subscription.customer_id,
                    subscription.plan_id,
                    subscription.status.value,
                    subscription.current_period_start.isoformat(),
                    subscription.current_period_end.isoformat(),
                    subscription.trial_end.isoformat() if subscription.trial_end else None,
                    subscription.discount_id,
                    subscription.past_due_since.isoformat() if subscription.past_due_since else None,
                )
            )
            sub_id = cur.lastrowid
        return Subscription(
            id=sub_id,
            customer_id=subscription.customer_id,
            plan_id=subscription.plan_id,
            status=subscription.status,
            current_period_start=subscription.current_period_start,
            current_period_end=subscription.current_period_end,
            trial_end=subscription.trial_end,
            discount_id=subscription.discount_id,
            past_due_since=subscription.past_due_since,
        )

    def get(self, subscription_id: int) -> Optional[Subscription]:
        with self.db.connect() as conn:
            row = conn.execute(
                """
                SELECT id, customer_id, plan_id, status,
                       current_period_start, current_period_end,
                       trial_end, discount_id, past_due_since
                FROM subscriptions WHERE id = ?
                """,
                (subscription_id,)
            ).fetchone()
        if row is None:
            return None
        return Subscription(
            id=row[0],
            customer_id=row[1],
            plan_id=row[2],
            status=SubscriptionStatus(row[3]),
            current_period_start=date.fromisoformat(row[4]),
            current_period_end=date.fromisoformat(row[5]),
            trial_end=date.fromisoformat(row[6]) if row[6] else None,
            discount_id=row[7],
            past_due_since=date.fromisoformat(row[8]) if row[8] else None,
        )

    def list_all(self) -> list[Subscription]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, customer_id, plan_id, status,
                       current_period_start, current_period_end,
                       trial_end, discount_id, past_due_since
                FROM subscriptions ORDER BY id
                """
            ).fetchall()
        return [
            Subscription(
                id=r[0],
                customer_id=r[1],
                plan_id=r[2],
                status=SubscriptionStatus(r[3]),
                current_period_start=date.fromisoformat(r[4]),
                current_period_end=date.fromisoformat(r[5]),
                trial_end=date.fromisoformat(r[6]) if r[6] else None,
                discount_id=r[7],
                past_due_since=date.fromisoformat(r[8]) if r[8] else None,
            )
            for r in rows
        ]

    def get_due_for_billing(self, as_of: date) -> list[Subscription]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, customer_id, plan_id, status,
                       current_period_start, current_period_end,
                       trial_end, discount_id, past_due_since
                FROM subscriptions
                WHERE (status = 'ACTIVE' AND current_period_end <= ?)
                   OR (status = 'TRIAL' AND trial_end <= ?)
                ORDER BY id
                """,
                (as_of.isoformat(), as_of.isoformat())
            ).fetchall()
        return [
            Subscription(
                id=r[0],
                customer_id=r[1],
                plan_id=r[2],
                status=SubscriptionStatus(r[3]),
                current_period_start=date.fromisoformat(r[4]),
                current_period_end=date.fromisoformat(r[5]),
                trial_end=date.fromisoformat(r[6]) if r[6] else None,
                discount_id=r[7],
                past_due_since=date.fromisoformat(r[8]) if r[8] else None,
            )
            for r in rows
        ]

    def update_period(self, subscription_id: int, new_start: date, new_end: date) -> None:
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE subscriptions SET current_period_start = ?, current_period_end = ? WHERE id = ?",
                (new_start.isoformat(), new_end.isoformat(), subscription_id)
            )

    def update_status(
        self,
        subscription_id: int,
        new_status: SubscriptionStatus,
        past_due_since: Optional[date] = None,
    ) -> None:
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE subscriptions SET status = ?, past_due_since = ? WHERE id = ?",
                (new_status.value, past_due_since.isoformat() if past_due_since else None, subscription_id)
            )

    def update_plan(self, subscription_id: int, new_plan_id: int) -> None:
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE subscriptions SET plan_id = ? WHERE id = ?",
                (new_plan_id, subscription_id)
            )


# ============================================================
# USAGE
# ============================================================
class UsageRecordRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def add(self, subscription_id: int, metric: str, quantity: int) -> int:
        with self.db.connect() as conn:
            cur = conn.execute(
                "INSERT INTO usage_records (subscription_id, metric, quantity) VALUES (?, ?, ?)",
                (subscription_id, metric, quantity)
            )
            return cur.lastrowid

    def sum_for_period(
        self, subscription_id: int, metric: str, period_start: date, period_end: date
    ) -> int:
        with self.db.connect() as conn:
            row = conn.execute(
                """
                SELECT COALESCE(SUM(quantity), 0)
                FROM usage_records
                WHERE subscription_id = ?
                  AND metric = ?
                  AND recorded_at >= ?
                  AND recorded_at < ?
                """,
                (subscription_id, metric, period_start.isoformat(), period_end.isoformat())
            ).fetchone()
        return row[0] if row else 0


# ============================================================
# INVOICES + LINE ITEMS
# ============================================================
class InvoiceRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def add(self, invoice: Invoice) -> Invoice:
        if invoice.id is not None:
            raise ValueError("invoice already has an id")
        with self.db.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO invoices (
                    subscription_id, period_start, period_end,
                    currency, subtotal, discount_total, tax_total, total,
                    status, issued_at, pdf_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    invoice.subscription_id,
                    invoice.period_start.isoformat(),
                    invoice.period_end.isoformat(),
                    invoice.subtotal.currency,
                    invoice.subtotal.to_storage(),
                    invoice.discount_total.to_storage(),
                    invoice.tax_total.to_storage(),
                    invoice.total.to_storage(),
                    invoice.status.value,
                    invoice.issued_at.isoformat() if invoice.issued_at else None,
                    invoice.pdf_path,
                )
            )
            inv_id = cur.lastrowid
        return Invoice(
            id=inv_id,
            subscription_id=invoice.subscription_id,
            period_start=invoice.period_start,
            period_end=invoice.period_end,
            subtotal=invoice.subtotal,
            discount_total=invoice.discount_total,
            tax_total=invoice.tax_total,
            total=invoice.total,
            status=invoice.status,
            issued_at=invoice.issued_at,
            pdf_path=invoice.pdf_path,
        )

    def get(self, invoice_id: int) -> Optional[Invoice]:
        with self.db.connect() as conn:
            row = conn.execute(
                """
                SELECT id, subscription_id, period_start, period_end,
                       currency, subtotal, discount_total, tax_total, total,
                       status, issued_at, pdf_path
                FROM invoices WHERE id = ?
                """,
                (invoice_id,)
            ).fetchone()
        if row is None:
            return None
        currency = row[4]
        return Invoice(
            id=row[0],
            subscription_id=row[1],
            period_start=date.fromisoformat(row[2]),
            period_end=date.fromisoformat(row[3]),
            subtotal=Money.from_storage(row[5], currency),
            discount_total=Money.from_storage(row[6], currency),
            tax_total=Money.from_storage(row[7], currency),
            total=Money.from_storage(row[8], currency),
            status=InvoiceStatus(row[9]),
            issued_at=datetime.fromisoformat(row[10]) if row[10] else None,
            pdf_path=row[11],
        )

    def count_for_subscription(self, subscription_id: int) -> int:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM invoices WHERE subscription_id = ?",
                (subscription_id,)
            ).fetchone()
        return row[0] if row else 0

    def mark_paid(self, invoice_id: int) -> None:
        with self.db.connect() as conn:
            conn.execute("UPDATE invoices SET status = 'PAID' WHERE id = ?", (invoice_id,))

    def mark_failed(self, invoice_id: int) -> None:
        with self.db.connect() as conn:
            conn.execute("UPDATE invoices SET status = 'FAILED' WHERE id = ?", (invoice_id,))

    def set_pdf_path(self, invoice_id: int, path: str) -> None:
        with self.db.connect() as conn:
            conn.execute("UPDATE invoices SET pdf_path = ? WHERE id = ?", (path, invoice_id))


class InvoiceLineItemRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def add(self, line_item: InvoiceLineItem) -> InvoiceLineItem:
        if line_item.id is not None:
            raise ValueError("line_item already has an id")
        with self.db.connect() as conn:
            cur = conn.execute(
                "INSERT INTO invoice_line_items (invoice_id, description, amount, kind) VALUES (?, ?, ?, ?)",
                (
                    line_item.invoice_id,
                    line_item.description,
                    line_item.amount.to_storage(),
                    line_item.kind.value,
                )
            )
            li_id = cur.lastrowid
        return InvoiceLineItem(
            id=li_id,
            invoice_id=line_item.invoice_id,
            description=line_item.description,
            amount=line_item.amount,
            kind=line_item.kind,
        )

    def list_for_invoice(self, invoice_id: int) -> list[InvoiceLineItem]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT id, invoice_id, description, amount, kind FROM invoice_line_items WHERE invoice_id = ?",
                (invoice_id,)
            ).fetchall()
        if not rows:
            return []
        # get currency from invoice
        with self.db.connect() as conn2:
            cur_row = conn2.execute(
                "SELECT currency FROM invoices WHERE id = ?",
                (invoice_id,)
            ).fetchone()
        if cur_row is None:
            raise ValueError(f"Invoice {invoice_id} not found")
        currency = cur_row[0]
        return [
            InvoiceLineItem(
                id=r[0],
                invoice_id=r[1],
                description=r[2],
                amount=Money.from_storage(r[3], currency),
                kind=LineItemKind(r[4]),
            )
            for r in rows
        ]


# ============================================================
# LEDGER — APPEND-ONLY
# ============================================================
class LedgerRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def add(self, entry: LedgerEntry) -> LedgerEntry:
        if entry.id is not None:
            raise ValueError("entry already has an id")
        with self.db.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO ledger_entries (
                    invoice_id, customer_id, amount, currency,
                    direction, reason, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.invoice_id,
                    entry.customer_id,
                    entry.amount.to_storage(),
                    entry.amount.currency,
                    entry.direction.value,
                    entry.reason,
                    entry.created_at.isoformat() if entry.created_at else None,
                )
            )
            entry_id = cur.lastrowid
        return LedgerEntry(
            id=entry_id,
            invoice_id=entry.invoice_id,
            customer_id=entry.customer_id,
            amount=entry.amount,
            direction=entry.direction,
            reason=entry.reason,
            created_at=entry.created_at,
        )

    def list_for_customer(self, customer_id: int) -> list[LedgerEntry]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, invoice_id, customer_id, amount, currency,
                       direction, reason, created_at
                FROM ledger_entries
                WHERE customer_id = ?
                ORDER BY created_at
                """,
                (customer_id,)
            ).fetchall()
        return [
            LedgerEntry(
                id=r[0],
                invoice_id=r[1],
                customer_id=r[2],
                amount=Money.from_storage(r[3], r[4]),
                direction=LedgerDirection(r[5]),
                reason=r[6],
                created_at=datetime.fromisoformat(r[7]) if r[7] else None,
            )
            for r in rows
        ]

    def update(self, *args, **kwargs):
        raise NotImplementedError("Ledger is append-only. Post a reversing entry instead.")

    def delete(self, *args, **kwargs):
        raise NotImplementedError("Ledger is append-only. Post a reversing entry instead.")


# ============================================================
# PAYMENT ATTEMPTS
# ============================================================
class PaymentAttemptRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def add(
        self,
        invoice_id: int,
        attempt_no: int,
        status: str,
        failure_reason: Optional[str],
        next_retry_at: Optional[datetime],
    ) -> int:
        with self.db.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO payment_attempts (
                    invoice_id, attempt_no, status, failure_reason, next_retry_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    invoice_id,
                    attempt_no,
                    status,
                    failure_reason,
                    next_retry_at.isoformat() if next_retry_at else None,
                )
            )
            return cur.lastrowid

    def list_for_invoice(self, invoice_id: int) -> list[dict]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, invoice_id, attempt_no, status, failure_reason,
                       attempted_at, next_retry_at
                FROM payment_attempts
                WHERE invoice_id = ?
                ORDER BY attempt_no
                """,
                (invoice_id,)
            ).fetchall()
        return [
            {
                "id": r[0],
                "invoice_id": r[1],
                "attempt_no": r[2],
                "status": r[3],
                "failure_reason": r[4],
                "attempted_at": r[5],
                "next_retry_at": r[6],
            }
            for r in rows
        ]

    def count_for_invoice(self, invoice_id: int) -> int:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM payment_attempts WHERE invoice_id = ?",
                (invoice_id,)
            ).fetchone()
        return row[0] if row else 0
