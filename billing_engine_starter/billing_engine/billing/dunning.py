"""
Dunning — payment retry logic.
"""

from datetime import date, timedelta
from typing import Optional
from enum import Enum

from billing_engine.payments.gateway import PaymentGateway
from billing_engine.models import Invoice, LedgerDirection, LedgerEntry, InvoiceStatus


RETRY_DELAYS_DAYS = [1, 3, 7]
MAX_ATTEMPTS = 3


class DunningState(str, Enum):
    PENDING = "PENDING"
    RETRY = "RETRY"
    FAILED = "FAILED"
    RECOVERED = "RECOVERED"


class DunningProcess:
    def __init__(
        self,
        gateway: PaymentGateway,
        invoice_repo,
        ledger_repo,
        subscription_repo,
        attempt_repo,
    ):
        self.gateway = gateway
        self.invoice_repo = invoice_repo
        self.ledger_repo = ledger_repo
        self.subscription_repo = subscription_repo
        self.attempt_repo = attempt_repo

    def attempt(self, invoice: Invoice, customer_id: int, today: date) -> DunningState:
        """Attempt to charge the invoice. Returns the new state."""
        # Record attempt number
        attempts = self.attempt_repo.count_for_invoice(invoice.id)
        attempt_no = attempts + 1

        result = self.gateway.charge(invoice.id, int(invoice.total.amount * 100), invoice.total.currency)

        if result.success:
            # Payment succeeded
            self.invoice_repo.mark_paid(invoice.id)
            # Credit ledger
            entry = LedgerEntry(
                id=None,
                invoice_id=invoice.id,
                customer_id=customer_id,
                amount=invoice.total,
                direction=LedgerDirection.CREDIT,
                reason=f"Payment for invoice #{invoice.id}",
                created_at=None,
            )
            self.ledger_repo.add(entry)
            # Record attempt
            self.attempt_repo.add(invoice.id, attempt_no, "SUCCESS", None, None)
            return DunningState.RECOVERED
        else:
            # Record failure
            next_retry = today + timedelta(days=RETRY_DELAYS_DAYS[min(attempt_no-1, len(RETRY_DELAYS_DAYS)-1)])
            self.attempt_repo.add(invoice.id, attempt_no, "FAILED", result.failure_reason, next_retry)

            if attempt_no >= MAX_ATTEMPTS:
                # Mark invoice as failed and subscription as past due
                self.invoice_repo.mark_failed(invoice.id)
                # Get subscription id from invoice
                self.subscription_repo.update_status(
                    invoice.subscription_id,
                    status=SubscriptionStatus.PAST_DUE,
                    past_due_since=today,
                )
                return DunningState.FAILED
            else:
                return DunningState.RETRY

    @staticmethod
    def should_cancel(past_due_since: date, today: date, grace_days: int = 7) -> bool:
        """Return True if the subscription should be canceled after grace period."""
        return (today - past_due_since).days >= grace_days
