from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    and_,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from contracts.bills import BillStatus
from core.db.base import ProductBase

SHA256_HEX_LENGTH = 64
CURRENCY_CODE_LENGTH = 3
AMOUNT = Numeric(18, 4)
USD_AMOUNT = Numeric(18, 2)
USD_PER_UNIT = Numeric(20, 10)
FX_SOURCE_LENGTH = 24
SOURCE_CONSTRAINT = "uq_bill_sources_owner_type_ref"


class BillSourceRow(ProductBase):
    __tablename__ = "bill_sources"
    __table_args__ = (
        UniqueConstraint("owner_id", "source_type", "source_ref", name=SOURCE_CONSTRAINT),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    source_type: Mapped[str]
    source_ref: Mapped[str]
    sender: Mapped[str] = mapped_column(default="")
    body_text: Mapped[str] = mapped_column(Text, default="")
    file_id: Mapped[UUID | None] = mapped_column(ForeignKey("files.id"), nullable=True)
    content_sha256: Mapped[str] = mapped_column(String(SHA256_HEX_LENGTH))
    attachment_sha256: Mapped[str | None] = mapped_column(String(SHA256_HEX_LENGTH), nullable=True)
    inbox_email_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("inbox_emails.id"), nullable=True
    )
    bill_id: Mapped[UUID | None] = mapped_column(ForeignKey("bills.id"), nullable=True, index=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class BillRow(ProductBase):
    __tablename__ = "bills"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str]
    payee_id: Mapped[UUID | None] = mapped_column(ForeignKey("payees.id"), nullable=True)
    payee_name: Mapped[str | None] = mapped_column(nullable=True)
    invoice_number: Mapped[str | None] = mapped_column(nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(AMOUNT, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(CURRENCY_CODE_LENGTH), nullable=True)
    amount_usd: Mapped[Decimal | None] = mapped_column(USD_AMOUNT, nullable=True)
    fx_usd_per_unit: Mapped[Decimal | None] = mapped_column(USD_PER_UNIT, nullable=True)
    fx_rate_date: Mapped[date | None] = mapped_column(nullable=True)
    fx_source: Mapped[str | None] = mapped_column(String(FX_SOURCE_LENGTH), nullable=True)
    category: Mapped[str | None] = mapped_column(nullable=True)
    due_date: Mapped[date | None] = mapped_column(nullable=True)
    candidate: Mapped[dict] = mapped_column(JSONB, default=dict)
    document_sha256: Mapped[str | None] = mapped_column(String(SHA256_HEX_LENGTH), nullable=True)
    fingerprint: Mapped[str | None] = mapped_column(String(SHA256_HEX_LENGTH), nullable=True)
    duplicate_of_bill_id: Mapped[UUID | None] = mapped_column(ForeignKey("bills.id"), nullable=True)
    status: Mapped[str] = mapped_column(default=BillStatus.DECIDING, index=True)
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


IS_CANONICAL_BILL = BillRow.duplicate_of_bill_id.is_(None)

Index(
    "uq_bills_owner_fingerprint",
    BillRow.owner_id,
    BillRow.fingerprint,
    unique=True,
    postgresql_where=and_(IS_CANONICAL_BILL, BillRow.fingerprint.is_not(None)),
)
Index(
    "uq_bills_owner_document",
    BillRow.owner_id,
    BillRow.document_sha256,
    unique=True,
    postgresql_where=and_(IS_CANONICAL_BILL, BillRow.document_sha256.is_not(None)),
)
Index("ix_bills_owner_payee_created", BillRow.owner_id, BillRow.payee_id, BillRow.created_at)
