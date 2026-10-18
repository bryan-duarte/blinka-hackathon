from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from contracts._base import ApiModel, StrictModel
from contracts.bills import BillSourceType
from contracts.files import EvidenceFileView
from contracts.guardrails import GuardrailViolation
from contracts.mail_gateway import MailAccountStatus, MailProvider
from contracts.payments import BillDecisionView
from contracts.pipeline import PipelineStageRecord
from contracts.whatsapp_gateway import WhatsAppConnectionMode


class InboxEmailStatus(StrEnum):
    RECEIVED = "received"
    PROCESSING = "processing"
    BLOCKED = "blocked"
    ANALYZING = "analyzing"
    PAID = "paid"
    HELD = "held"
    REVIEW = "review"
    DUPLICATE = "duplicate"
    NO_INVOICE = "no_invoice"
    NO_INFO = "no_info"
    ERROR = "error"


InboxChannel = Literal["email", "whatsapp"]

SOURCE_TYPE_BY_PROVIDER: dict[MailProvider, BillSourceType] = {
    MailProvider.GMAIL: BillSourceType.EMAIL,
    MailProvider.OUTLOOK: BillSourceType.EMAIL,
    MailProvider.SIMULATED: BillSourceType.EMAIL,
    MailProvider.WHATSAPP: BillSourceType.WHATSAPP,
}
PROVIDERS_BY_CHANNEL: dict[InboxChannel, frozenset[MailProvider]] = {
    "email": frozenset({MailProvider.GMAIL, MailProvider.OUTLOOK, MailProvider.SIMULATED}),
    "whatsapp": frozenset({MailProvider.WHATSAPP}),
}


class MailboxConnectionRecord(StrictModel):
    connection_id: UUID
    owner_id: UUID
    provider: MailProvider
    connected_account_id: str
    trigger_id: str | None
    status: MailAccountStatus
    created_at: datetime
    mode: WhatsAppConnectionMode | None = None
    phone_number: str | None = None
    external_ref: str | None = None


class InboxEmailRecord(StrictModel):
    email_id: UUID
    owner_id: UUID
    provider: MailProvider
    sender: str
    subject: str
    body: str
    received_at: datetime | None
    status: InboxEmailStatus
    violations: list[GuardrailViolation]
    run_id: UUID | None
    error: str | None
    pipeline_stages: list[PipelineStageRecord] = []


class QueuedEmail(StrictModel):
    email_id: UUID
    owner_id: UUID
    source_payload: dict


class ConnectMailboxRequest(ApiModel):
    provider: Literal[MailProvider.GMAIL, MailProvider.OUTLOOK]


class ConfirmMailboxRequest(ApiModel):
    connected_account_id: str


class MailboxConnectStarted(ApiModel):
    connection_id: UUID
    redirect_url: str


class MailboxConnectionView(ApiModel):
    connection_id: UUID
    provider: MailProvider
    status: MailAccountStatus
    created_at: datetime
    mode: WhatsAppConnectionMode | None = None
    phone_number: str | None = None
    sandbox_number: str | None = None


class InboxEmailView(ApiModel):
    email_id: UUID
    provider: MailProvider
    sender: str
    subject: str
    preview: str
    received_at: datetime | None
    status: InboxEmailStatus
    decision: BillDecisionView | None = None
    source_type: BillSourceType = BillSourceType.EMAIL


class InboxEmailDetail(InboxEmailView):
    body: str
    violations: list[GuardrailViolation] = []
    error: str | None = None
    run_id: UUID | None = None
    evidence: list[EvidenceFileView] = []
    pipeline_stages: list[PipelineStageRecord] = []
