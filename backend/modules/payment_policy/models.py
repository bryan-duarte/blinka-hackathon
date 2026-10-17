from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Index, Numeric, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from contracts.payment_policy import PayeeStatus
from core.db.base import ProductBase

USD_AMOUNT = Numeric(18, 2)
CONFIDENCE = Numeric(3, 2)
PERCENTAGE = Numeric(5, 2)
PAYEE_NAME_CONSTRAINT = "uq_payees_owner_name"
PAYEE_IDENTIFIER_CONSTRAINT = "uq_payee_identifiers_owner_kind_value"
BLACKLIST_CONSTRAINT = "uq_blacklist_entries_owner_kind_value"


class PaymentPolicyRow(ProductBase):
    __tablename__ = "payment_policies"
    __table_args__ = (
        UniqueConstraint("owner_id", "version", name="uq_payment_policies_owner_version"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    version: Mapped[int]
    is_active: Mapped[bool] = mapped_column(default=True)
    hard_cap_per_payment_usd: Mapped[Decimal] = mapped_column(USD_AMOUNT)
    auto_pay_max_usd: Mapped[Decimal] = mapped_column(USD_AMOUNT)
    monthly_budget_usd: Mapped[Decimal] = mapped_column(USD_AMOUNT)
    category_monthly_budgets_usd: Mapped[dict] = mapped_column(JSONB, default=dict)
    allowed_categories: Mapped[list] = mapped_column(JSONB, default=list)
    allowed_currencies: Mapped[list] = mapped_column(JSONB, default=list)
    duplicate_window_days: Mapped[int]
    min_field_confidence: Mapped[Decimal] = mapped_column(CONFIDENCE)
    min_category_confidence: Mapped[Decimal] = mapped_column(CONFIDENCE)
    checker_review_low: Mapped[Decimal] = mapped_column(CONFIDENCE)
    checker_review_high: Mapped[Decimal] = mapped_column(CONFIDENCE)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


Index(
    "uq_payment_policies_owner_active",
    PaymentPolicyRow.owner_id,
    unique=True,
    postgresql_where=PaymentPolicyRow.is_active.is_(True),
)


class PayeeRow(ProductBase):
    __tablename__ = "payees"
    __table_args__ = (UniqueConstraint("owner_id", "normalized_name", name=PAYEE_NAME_CONSTRAINT),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str]
    display_name: Mapped[str]
    normalized_name: Mapped[str]
    status: Mapped[str] = mapped_column(default=PayeeStatus.ALLOWED)
    payment_method: Mapped[str]
    default_category: Mapped[str | None] = mapped_column(nullable=True)
    currency: Mapped[str]
    per_payment_max_usd: Mapped[Decimal | None] = mapped_column(USD_AMOUNT, nullable=True)
    monthly_budget_usd: Mapped[Decimal | None] = mapped_column(USD_AMOUNT, nullable=True)
    agreed_amount_usd: Mapped[Decimal | None] = mapped_column(USD_AMOUNT, nullable=True)
    agreed_tolerance_pct: Mapped[Decimal | None] = mapped_column(PERCENTAGE, nullable=True)
    attributes: Mapped[dict] = mapped_column(JSONB, default=dict)
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class PayeeIdentifierRow(ProductBase):
    __tablename__ = "payee_identifiers"
    __table_args__ = (
        UniqueConstraint("owner_id", "kind", "normalized_value", name=PAYEE_IDENTIFIER_CONSTRAINT),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    payee_id: Mapped[UUID] = mapped_column(ForeignKey("payees.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str]
    normalized_value: Mapped[str]
    raw_value: Mapped[str]


class BlacklistEntryRow(ProductBase):
    __tablename__ = "blacklist_entries"
    __table_args__ = (
        UniqueConstraint("owner_id", "kind", "normalized_value", name=BLACKLIST_CONSTRAINT),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[str]
    normalized_value: Mapped[str]
    reason: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
