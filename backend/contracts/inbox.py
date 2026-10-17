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


class SimulatedEmailKind(StrEnum):
    INVOICE_USD = "invoice_usd"
    INVOICE_USD_PDF = "invoice_usd_pdf"
    INVOICE_ZIP_XML = "invoice_zip_xml"
    SCANNED_PDF = "scanned_pdf"
    INVOICE_CLP = "invoice_clp"
    AWS_CARD = "aws_card"
    AWS_IMPERSONATION = "aws_impersonation"
    AMAZ0N_BLACKLISTED = "amaz0n_blacklisted"
    OVER_AUTO_PAY = "over_auto_pay"
    OVER_HARD_CAP = "over_hard_cap"
    UNKNOWN_PAYEE = "unknown_payee"
    NO_CURRENCY = "no_currency"
    PERSON_CUENTA_COBRO = "person_cuenta_cobro"
    PERSON_CUENTA_COBRO_SECOND = "person_cuenta_cobro_second"
    AGREEMENT_MISMATCH = "agreement_mismatch"
    PROMPT_INJECTION = "prompt_injection"
    PLAIN = "plain"


class MailboxConnectionRecord(StrictModel):
    connection_id: UUID
    owner_id: UUID
    provider: MailProvider
    connected_account_id: str
    trigger_id: str | None
    status: MailAccountStatus
    created_at: datetime


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


class ConnectMailboxRequest(ApiModel):
    provider: Literal[MailProvider.GMAIL, MailProvider.OUTLOOK]


class ConfirmMailboxRequest(ApiModel):
    connected_account_id: str


class SimulateEmailRequest(ApiModel):
    kind: SimulatedEmailKind


class MailboxConnectStarted(ApiModel):
    connection_id: UUID
    redirect_url: str


class MailboxConnectionView(ApiModel):
    connection_id: UUID
    provider: MailProvider
    status: MailAccountStatus
    created_at: datetime


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
