from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Identity, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from contracts.payments import RunStatus
from core.db.base import ProductBase


class AgentRun(ProductBase):
    __tablename__ = "agent_runs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    agent: Mapped[str]
    status: Mapped[str] = mapped_column(default=RunStatus.PENDING, index=True)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    file_id: Mapped[UUID | None] = mapped_column(ForeignKey("files.id"), nullable=True)
    session_id: Mapped[UUID | None] = mapped_column(ForeignKey("sessions.id"), nullable=True)
    error: Mapped[str | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class AgentRunEvent(ProductBase):
    __tablename__ = "agent_run_events"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("agent_runs.id"), index=True)
    step: Mapped[str]
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
