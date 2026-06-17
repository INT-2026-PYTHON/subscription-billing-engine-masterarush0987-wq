"""
Dunning — payment retry logic.
"""

from datetime import date, timedelta
from dataclasses import dataclass
from enum import Enum

from billing_engine.payments.gateway import PaymentGateway
from billing_engine.models import Invoice, LedgerDirection, LedgerEntry, InvoiceStatus, SubscriptionStatus


RETRY_DELAYS_DAYS = [1, 3, 7]
MAX_ATTEMPTS = 3


class DunningState(str, Enum):
    RETRYING = "RETRYING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


@dataclass
class DunningOutcome:
    state: DunningState
    next_retry_at: Optional[date] = None


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

    def attempt(self, invoice: Invoice, customer_id: int, today: date) -> DunningOutcome:
        """Attempt to charge the invoice. Returns an outcome with state."""
        attempts = self.attempt_repo.count_for_invoice(invoice.id)
        attempt_no = attempts + 1

        result = self.gateway.charge(invoice.id, int(invoice.total.amount * 100), invoice.total.currency)

        if result.success:
            self.invoice_repo.mark_paid(invoice.id)
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
            self.attempt_repo.add(invoice.id, attempt_no, "SUCCESS", None, None)
            return DunningOutcome(state=DunningState.SUCCEEDED)
        else:
            next_retry = today + timedelta(days=RETRY_DELAYS_DAYS[min(attempt_no-1, len(RETRY_DELAYS_DAYS)-1)])
            self.attempt_repo.add(invoice.id, attempt_no, "FAILED", result.failure_reason, next_retry)

            if attempt_no >= MAX_ATTEMPTS:
                self.invoice_repo.mark_failed(invoice.id)
                self.subscription_repo.update_status(
                    invoice.subscription_id,
                    SubscriptionStatus.PAST_DUE,
                    past_due_since=today,
                )
                return DunningOutcome(state=DunningState.FAILED)
            else:
                return DunningOutcome(state=DunningState.RETRYING, next_retry_at=next_retry)

    @staticmethod
    def should_cancel(past_due_since: date, today: date, grace_days: int = 7) -> bool:
        return (today - past_due_since).days >= grace_days
