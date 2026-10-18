from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from contracts._base import ApiModel, StrictModel
from contracts.payment_policy import PaymentCategory
from contracts.payments import Verdict

HumanAction = Literal["approved", "rejected"]


class DecisionMemoryInput(StrictModel):
    owner_id: UUID
    actor_user_id: UUID
    bill_id: UUID
    payee_id: UUID | None
    payee_name: str | None
    amount: Decimal | None
    currency: str | None
    amount_usd: Decimal | None
    category: PaymentCategory | None
    escalation_reasons: list[str]
    human_action: HumanAction
    resulting_verdict: Verdict
    note: str
    decided_at: datetime


class MemoryPrecedent(StrictModel):
    memory_id: str
    situation: str
    human_action: HumanAction
    lesson: str
    applies_when: str | None
    decided_at: datetime | None
    score: float | None


class MemoryView(ApiModel):
    memory_id: str
    payee_key: str
    payee: str
    situation: str
    human_action: HumanAction
    lesson: str
    applies_when: str | None
    source_bill_id: UUID | None
    note_excerpt: str | None
    created_at: datetime
    updated_at: datetime
