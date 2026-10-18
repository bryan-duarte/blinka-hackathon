from datetime import datetime
from enum import StrEnum
from typing import Literal

from contracts._base import ApiModel, StrictModel

MAX_EVIDENCE_ATTACHMENTS = 10


class MailProvider(StrEnum):
    GMAIL = "gmail"
    OUTLOOK = "outlook"
    SIMULATED = "simulated"
    WHATSAPP = "whatsapp"


class MailAccountStatus(StrEnum):
    INITIATED = "initiated"
    ACTIVE = "active"
    FAILED = "failed"
    EXPIRED = "expired"


class MailboxLink(StrictModel):
    connected_account_id: str
    redirect_url: str


class MailTriggerEvent(StrictModel):
    provider: MailProvider
    user_id: str
    connected_account_id: str
    message_id: str
    data: dict


class FetchedAttachment(StrictModel):
    filename: str
    mime: str
    content: bytes


class FetchedEmail(StrictModel):
    sender: str
    subject: str
    body: str
    received_at: datetime | None = None
    attachments: list[FetchedAttachment] = []


class WebhookAccepted(ApiModel):
    status: Literal["accepted"] = "accepted"
