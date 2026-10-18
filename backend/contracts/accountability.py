from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import Field

from contracts._base import ApiModel, StrictModel
from contracts.bills import BillSourceType, BillStatus
from contracts.fx import FxSource
from contracts.inbox import InboxEmailStatus
from contracts.payment_policy import PayeeKind, PaymentCategory
from contracts.payments import DecisionActor, RuleEffect, RunStatus, Verdict

PERIOD_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"
CURRENCY_CODE_PATTERN = r"^[A-Z]{3}$"

LedgerTab = Literal["all", "paid", "escalated", "stopped"]


class LedgerOutcome(StrEnum):
    PAID = "paid"
    ESCALATED = "escalated"
    HELD = "held"
    APPROVED_BY_HUMAN = "approved_by_human"
    REJECTED_BY_HUMAN = "rejected_by_human"
    DUPLICATE = "duplicate"
    BLOCKED = "blocked"
    NOT_AN_INVOICE = "not_an_invoice"
    MISSING_INFO = "missing_info"
    ERROR = "error"


LEDGER_TAB_OUTCOMES: dict[LedgerTab, frozenset[LedgerOutcome]] = {
    "paid": frozenset({LedgerOutcome.PAID, LedgerOutcome.APPROVED_BY_HUMAN}),
    "escalated": frozenset({LedgerOutcome.ESCALATED}),
    "stopped": frozenset(
        {
            LedgerOutcome.HELD,
            LedgerOutcome.REJECTED_BY_HUMAN,
            LedgerOutcome.DUPLICATE,
            LedgerOutcome.BLOCKED,
            LedgerOutcome.NOT_AN_INVOICE,
            LedgerOutcome.MISSING_INFO,
            LedgerOutcome.ERROR,
        }
    ),
}


class DecisionLedgerRow(StrictModel):
    decision_id: UUID
    decided_at: datetime
    actor: DecisionActor
    verdict: Verdict
    rule_results: list[dict]
    explanation: str
    note: str | None
    run_id: UUID | None
    bill_id: UUID
    bill_status: BillStatus
    duplicate_of_bill_id: UUID | None
    payee_id: UUID | None
    payee_name: str | None
    payee_kind: PayeeKind | None
    category: PaymentCategory | None
    amount: Decimal | None
    currency: str | None
    amount_usd: Decimal | None
    fx_usd_per_unit: Decimal | None
    fx_rate_date: date | None
    fx_source: FxSource | None
    source_type: BillSourceType | None
    inbox_email_id: UUID | None
    subject: str | None


class InboxLedgerRow(StrictModel):
    inbox_email_id: UUID
    occurred_at: datetime
    status: InboxEmailStatus
    violations: list[dict]
    error: str | None
    subject: str
    source_type: BillSourceType
    run_id: UUID | None
    run_status: RunStatus | None
    has_extraction_failed: bool


class RunListRow(StrictModel):
    run_id: UUID
    status: RunStatus
    created_at: datetime
    updated_at: datetime
    error: str | None
    bill_id: UUID | None
    source_type: BillSourceType | None
    sender: str | None
    inbox_email_id: UUID | None
    subject: str | None
    verdict: Verdict | None
    tool_count: int


class LedgerFilters(ApiModel):
    period: str | None = Field(default=None, pattern=PERIOD_PATTERN)
    tab: LedgerTab = "all"
    payee_id: UUID | None = None
    currency: str | None = Field(default=None, pattern=CURRENCY_CODE_PATTERN)


class LedgerReason(ApiModel):
    rule_id: str
    name: str
    effect: RuleEffect
    reason: str


class LedgerEntryView(ApiModel):
    entry_id: UUID
    occurred_at: datetime
    outcome: LedgerOutcome
    actor: DecisionActor
    payee_id: UUID | None
    payee_name: str | None
    payee_kind: PayeeKind | None
    category: PaymentCategory | None
    amount: Decimal | None
    currency: str | None
    amount_usd: Decimal | None
    fx_usd_per_unit: Decimal | None
    fx_rate_date: date | None
    fx_source: FxSource | None
    reasons: list[LedgerReason]
    explanation: str
    note: str | None
    channel: BillSourceType | None
    subject: str | None
    bill_id: UUID | None
    run_id: UUID | None
    inbox_email_id: UUID | None
    is_seeded: bool


class LedgerKpis(ApiModel):
    paid_count: int
    paid_usd: Decimal
    escalated_count: int
    escalated_usd: Decimal
    stopped_count: int
    stopped_usd: Decimal
    auto_pay_rate: Decimal


class LedgerTimelinePoint(ApiModel):
    bucket: date
    paid: int
    escalated: int
    stopped: int


class LimitUsage(ApiModel):
    scope: str
    label: str
    payee_currency: str | None
    spent_usd: Decimal
    limit_usd: Decimal | None


class ReasonCount(ApiModel):
    rule_id: str
    name: str
    count: int


class CurrencyTotal(ApiModel):
    currency: str
    amount: Decimal
    amount_usd: Decimal
    count: int


class LedgerSummaryView(ApiModel):
    period: str
    kpis: LedgerKpis
    timeline: list[LedgerTimelinePoint]
    limits: list[LimitUsage]
    top_reasons: list[ReasonCount]
    currencies: list[CurrencyTotal]


class RunListItemView(ApiModel):
    run_id: UUID
    status: RunStatus
    created_at: datetime
    duration_ms: int | None
    channel: BillSourceType | None
    sender: str | None
    subject: str | None
    verdict: Verdict | None
    bill_id: UUID | None
    inbox_email_id: UUID | None
    tool_count: int
    error: str | None
