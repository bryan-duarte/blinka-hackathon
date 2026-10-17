from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import PaymentsBase, ProductBase


class SessionRecord(ProductBase):
    __tablename__ = "sessions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(default="")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class SessionExecution(PaymentsBase):
    __tablename__ = "session_executions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID]
    agent: Mapped[str]
    input_summary: Mapped[str]
    output_summary: Mapped[str]
    occurred_at: Mapped[datetime] = mapped_column(server_default=func.now())
