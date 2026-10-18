from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    ForeignKey,
    Identity,
    Index,
    Numeric,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from contracts.payments import RunStatus
from core.db.base import ProductBase

ACTIVE_RUN_STATUSES = (RunStatus.PENDING, RunStatus.RUNNING)
PERIOD_LENGTH = 7
CURRENCY_CODE_LENGTH = 3
EVIDENCE_ROLE_LENGTH = 16
AMOUNT = Numeric(18, 4)
USD_AMOUNT = Numeric(18, 2)
USD_PER_UNIT = Numeric(20, 10)
FX_SOURCE_LENGTH = 24
PAYMENT_BILL_CONSTRAINT = "uq_payments_bill_id"
BUDGET_COUNTER_CONSTRAINT = "pk_budget_counters"


class AgentRun(ProductBase):
    __tablename__ = "agent_runs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    agent: Mapped[str]
    status: Mapped[str] = mapped_column(default=RunStatus.PENDING, index=True)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    file_id: Mapped[UUID | None] = mapped_column(ForeignKey("files.id"), nullable=True)
    bill_source_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("bill_sources.id"), nullable=True, index=True
    )
    bill_id: Mapped[UUID | None] = mapped_column(ForeignKey("bills.id"), nullable=True, index=True)
    error: Mapped[str | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


Index(
    "uq_agent_runs_active_source",
    AgentRun.bill_source_id,
    unique=True,
    postgresql_where=AgentRun.status.in_(ACTIVE_RUN_STATUSES),
)


class AgentRunEvent(ProductBase):
    __tablename__ = "agent_run_events"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("agent_runs.id"), index=True)
    step: Mapped[str]
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class AgentRunFileRow(ProductBase):
    __tablename__ = "agent_run_files"
    __table_args__ = (UniqueConstraint("bill_source_id", "file_id"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("agent_runs.id"), nullable=True, index=True
    )
    bill_source_id: Mapped[UUID] = mapped_column(ForeignKey("bill_sources.id"))
    file_id: Mapped[UUID] = mapped_column(ForeignKey("files.id"), index=True)
    role: Mapped[str] = mapped_column(String(EVIDENCE_ROLE_LENGTH))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class PaymentDecisionRow(ProductBase):
    __tablename__ = "payment_decisions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    bill_id: Mapped[UUID] = mapped_column(ForeignKey("bills.id"), index=True)
    run_id: Mapped[UUID | None] = mapped_column(ForeignKey("agent_runs.id"), nullable=True)
    actor: Mapped[str]
    actor_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    verdict: Mapped[str]
    rule_results: Mapped[list] = mapped_column(JSONB, default=list)
    checker: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    explanation: Mapped[str] = mapped_column(Text)
    policy_id: Mapped[UUID | None] = mapped_column(ForeignKey("payment_policies.id"), nullable=True)
    policy_version: Mapped[int | None] = mapped_column(nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class PaymentRow(ProductBase):
    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint("bill_id", name=PAYMENT_BILL_CONSTRAINT),
        UniqueConstraint("idempotency_key", name="uq_payments_idempotency_key"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    bill_id: Mapped[UUID] = mapped_column(ForeignKey("bills.id"))
    idempotency_key: Mapped[str]
    payee_id: Mapped[UUID | None] = mapped_column(ForeignKey("payees.id"), nullable=True)
    amount: Mapped[Decimal] = mapped_column(AMOUNT)
    currency: Mapped[str] = mapped_column(String(CURRENCY_CODE_LENGTH))
    amount_usd: Mapped[Decimal] = mapped_column(USD_AMOUNT)
    fx_usd_per_unit: Mapped[Decimal | None] = mapped_column(USD_PER_UNIT, nullable=True)
    fx_rate_date: Mapped[date | None] = mapped_column(nullable=True)
    fx_source: Mapped[str | None] = mapped_column(String(FX_SOURCE_LENGTH), nullable=True)
    category: Mapped[str | None] = mapped_column(nullable=True)
    period: Mapped[str] = mapped_column(String(PERIOD_LENGTH))
    scopes: Mapped[list] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(index=True)
    rail_reference: Mapped[str | None] = mapped_column(nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class BudgetCounterRow(ProductBase):
    __tablename__ = "budget_counters"
    __table_args__ = (
        PrimaryKeyConstraint("owner_id", "scope", "period", name=BUDGET_COUNTER_CONSTRAINT),
    )

    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    scope: Mapped[str]
    period: Mapped[str] = mapped_column(String(PERIOD_LENGTH))
    reserved_usd: Mapped[Decimal] = mapped_column(USD_AMOUNT, default=Decimal("0"))
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
