from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from contracts.memory import HumanAction
from contracts.payments import Verdict


class PaymentPrecedent(BaseModel):
    """A reusable lesson from a finance person's decision on an escalated invoice.

    Store the generalisable rule, not the raw note. One precedent per distinct lesson."""

    payee: str = Field(description="Payee display name the lesson applies to.")
    situation: str = Field(
        description="What made the invoice unusual, for example 'amount 40% above agreed'."
    )
    human_action: HumanAction = Field(description="What the person decided.")
    lesson: str = Field(description="Standalone guidance for future invoices from this payee.")
    applies_when: str | None = Field(
        default=None,
        description="Conditions or limits, for example 'Q1 workshop invoices up to $5,000'.",
    )


class PrecedentSource(BaseModel):
    bill_id: UUID
    verdict: Verdict
    actor_user_id: UUID
    note_excerpt: str
    decided_at: datetime
