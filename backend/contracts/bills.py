from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from contracts._base import ApiModel, StrictModel
from contracts.fx import FxSource
from contracts.payment_policy import PayeeKind, PaymentCategory


class BillSourceType(StrEnum):
    EMAIL = "email"
    CHAT = "chat"
    UPLOAD = "upload"
    TELEGRAM = "telegram"
    WHATSAPP = "whatsapp"


UPLOAD_SOURCE_REF_PREFIX = "upload:"


class BillStatus(StrEnum):
    DECIDING = "deciding"
    PAID = "paid"
    HELD = "held"
    REVIEW = "review"
    APPROVING = "approving"
    REJECTED = "rejected"
    DUPLICATE = "duplicate"


class BillSourceIntake(StrictModel):
    owner_id: UUID
    source_type: BillSourceType
    source_ref: str
    sender: str
    body_text: str
    file_id: UUID | None
    attachment_sha256: str | None
    inbox_email_id: UUID | None = None
    received_at: datetime | None = None


class BillSourceRecord(StrictModel):
    source_id: UUID
    owner_id: UUID
    source_type: BillSourceType
    source_ref: str
    sender: str
    body_text: str
    file_id: UUID | None
    content_sha256: str
    attachment_sha256: str | None
    inbox_email_id: UUID | None
    bill_id: UUID | None
    received_at: datetime | None
    created_at: datetime


class SourceRegistration(StrictModel):
    source: BillSourceRecord
    is_new: bool


class BillDocument(StrictModel):
    body_text: str
    file_id: UUID | None
    sender: str


class BillRecord(StrictModel):
    bill_id: UUID
    owner_id: UUID
    kind: PayeeKind
    payee_id: UUID | None
    payee_name: str | None
    invoice_number: str | None
    amount: Decimal | None
    currency: str | None
    amount_usd: Decimal | None
    fx_usd_per_unit: Decimal | None = None
    fx_rate_date: date | None = None
    fx_source: FxSource | None = None
    category: PaymentCategory | None
    due_date: date | None
    candidate: dict
    document_sha256: str | None
    fingerprint: str | None
    duplicate_of_bill_id: UUID | None
    status: BillStatus
    version: int
    created_at: datetime
    updated_at: datetime


class BillFields(StrictModel):
    kind: PayeeKind
    payee_id: UUID | None
    payee_name: str | None
    normalized_payee_name: str | None
    invoice_number: str | None
    amount: Decimal | None
    currency: str | None
    amount_usd: Decimal | None
    fx_usd_per_unit: Decimal | None = None
    fx_rate_date: date | None = None
    fx_source: FxSource | None = None
    category: PaymentCategory | None
    due_date: date | None
    candidate: dict


class BillClaim(StrictModel):
    bill: BillRecord
    duplicate_of: BillRecord | None


class BillSummary(StrictModel):
    bill_id: UUID
    invoice_number: str | None
    amount_usd: Decimal | None
    due_date: date | None
    status: BillStatus
    created_at: datetime


class BillSourceView(ApiModel):
    source_id: UUID
    source_type: BillSourceType
    source_ref: str
    sender: str
    file_id: UUID | None
    inbox_email_id: UUID | None
    received_at: datetime | None
    created_at: datetime
