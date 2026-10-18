from datetime import datetime
from enum import StrEnum

from pydantic import Field

from contracts._base import ApiModel, StrictModel


class PromptId(StrEnum):
    PAYMENTS_AGENT = "payments_agent"
    BILL_CLASSIFICATION = "bill_classification"
    SERVICE_EXTRACTION = "service_extraction"
    PERSON_EXTRACTION = "person_extraction"
    COMPANY_EXTRACTION = "company_extraction"
    PAYMENT_CHECKER = "payment_checker"
    EMAIL_TRIAGE = "email_triage"
    MEMORY_PRECEDENT = "memory_precedent"


class EmailMessage(StrictModel):
    sender: str
    subject: str
    body: str
    received_at: datetime | None = None


class EmailCategory(StrEnum):
    ACTION_REQUIRED = "action_required"
    INFORMATIONAL = "informational"
    MEETING = "meeting"
    NEWSLETTER = "newsletter"
    SPAM = "spam"
    PERSONAL = "personal"
    OTHER = "other"


class EmailPriority(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EmailTriage(ApiModel):
    """Final step: call this exactly once with the triage of the email."""

    category: EmailCategory
    priority: EmailPriority
    summary: str = Field(description="One or two sentences.")
    action_items: list[str] = []
    requires_reply: bool
