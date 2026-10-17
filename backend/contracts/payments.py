from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import Field

from contracts._base import ApiModel, StrictModel
from contracts.bills import BillSourceView, BillStatus
from contracts.files import EvidenceFileView, EvidenceLink
from contracts.payment_candidates import PaymentCandidate
from contracts.payment_policy import PaymentCategory

REVIEW_NOTE_MIN_LENGTH = 3
REVIEW_NOTE_MAX_LENGTH = 500

CheckerQuestionId = Literal["CHK1", "CHK2", "CHK3"]


class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Verdict(StrEnum):
    PAY = "pay"
    HOLD = "hold"
    REVIEW = "review"


class RuleEffect(StrEnum):
    PASS = "pass"
    HOLD = "hold"
    REVIEW = "review"


class DecisionActor(StrEnum):
    AGENT = "agent"
    HUMAN = "human"


class LedgerStatus(StrEnum):
    RESERVED = "reserved"
    EXECUTED = "executed"


class PaymentRunRecord(StrictModel):
    run_id: UUID
    status: RunStatus
    error: str | None = None
    bill_source_id: UUID | None = None
    bill_id: UUID | None = None


class PaymentRunTrigger(ApiModel):
    bill_source_id: UUID
    session_id: UUID | None = None
    evidence: list[EvidenceLink] = []


class UploadRunRequest(ApiModel):
    file_id: UUID


class PaymentRunAccepted(ApiModel):
    run_id: UUID
    status: RunStatus
    duplicate: bool = False


class PaymentRunEvent(StrictModel):
    step: str
    payload: dict = {}
    created_at: datetime


class RuleResult(ApiModel):
    rule_id: str
    name: str
    effect: RuleEffect
    reason: str
    evidence: dict[str, str] = {}


class CheckerAnswer(ApiModel):
    question_id: CheckerQuestionId
    probability: float = Field(ge=0, le=1)
    rationale: str = Field(description="One sentence in Spanish.")


class CheckerAssessment(ApiModel):
    """Final step: answer each question once with a probability in [0, 1]."""

    answers: list[CheckerAnswer]


class DecisionRecord(StrictModel):
    decision_id: UUID | None = None
    bill_id: UUID
    run_id: UUID | None
    actor: DecisionActor
    actor_user_id: UUID | None
    verdict: Verdict
    rule_results: list[RuleResult]
    checker: CheckerAssessment | None
    explanation: str
    policy_id: UUID | None
    policy_version: int | None
    note: str | None = None
    created_at: datetime | None = None


class PaymentRecord(StrictModel):
    payment_id: UUID
    owner_id: UUID
    bill_id: UUID
    idempotency_key: str
    payee_id: UUID | None
    amount: Decimal
    currency: str
    amount_usd: Decimal
    category: PaymentCategory | None
    period: str
    scopes: list[str]
    status: LedgerStatus
    rail_reference: str | None
    executed_at: datetime | None
    created_at: datetime


class BillDecisionView(ApiModel):
    bill_id: UUID
    verdict: Verdict
    status: BillStatus
    explanation: str
    rule_results: list[RuleResult]
    checker: CheckerAssessment | None
    candidate: PaymentCandidate | None
    payee_id: UUID | None
    payee_name: str | None
    amount: Decimal | None
    currency: str | None
    amount_usd: Decimal | None
    category: PaymentCategory | None
    duplicate_of_bill_id: UUID | None
    actor: DecisionActor
    note: str | None
    decided_at: datetime
    can_approve: bool


class PaymentView(ApiModel):
    payment_id: UUID
    status: LedgerStatus
    amount: Decimal
    currency: str
    amount_usd: Decimal
    period: str
    rail_reference: str | None
    executed_at: datetime | None


class BillDetail(ApiModel):
    decision: BillDecisionView
    history: list[BillDecisionView]
    sources: list[BillSourceView]
    payment: PaymentView | None
    evidence: list[EvidenceFileView] = []


class BudgetUsageView(ApiModel):
    scope: str
    limit_usd: Decimal | None
    reserved_usd: Decimal


class ReviewActionRequest(ApiModel):
    note: str = Field(min_length=REVIEW_NOTE_MIN_LENGTH, max_length=REVIEW_NOTE_MAX_LENGTH)


class PaymentRunStatus(ApiModel):
    run_id: UUID
    status: RunStatus
    error: str | None = None
    events: list[PaymentRunEvent] = []
    decision: BillDecisionView | None = None
    is_bill: bool | None = None
    extraction_failed: bool = False
    evidence: list[EvidenceFileView] = []
