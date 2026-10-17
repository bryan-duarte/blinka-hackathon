from datetime import datetime
from enum import StrEnum

from pydantic import Field

from contracts._base import ApiModel, StrictModel


class PromptId(StrEnum):
    MAIN_AGENT = "main_agent"
    PAYMENT_AGENT = "payment_agent"
    INVOICE_EXTRACTION = "invoice_extraction"
    EMAIL_TRIAGE = "email_triage"
    HELLO_WORLD = "hello_world"


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


class HelloWorldReport(ApiModel):
    """Final step: call this exactly once after calling both diagnostic tools."""

    greeting: str
    token: str = Field(description="The exact token returned by get_random_token.")
    token_generated_at: str = Field(
        description="The exact generated_at returned by get_random_token."
    )
    system_name: str = Field(description="The name field returned by get_system_profile.")
    tools_called: list[str]
