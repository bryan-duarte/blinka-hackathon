from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from contracts.inbox import InboxEmailStatus
from contracts.mail_gateway import MailAccountStatus
from contracts.whatsapp_gateway import WhatsAppConnectionMode
from core.db.base import ProductBase

ACTIVE_SANDBOX_CONNECTION = text(
    f"mode = '{WhatsAppConnectionMode.SANDBOX}' AND status = '{MailAccountStatus.ACTIVE}'"
)


class MailboxConnection(ProductBase):
    __tablename__ = "mailbox_connections"
    __table_args__ = (
        Index(
            "uq_mailbox_connections_sandbox_phone",
            "phone_number",
            unique=True,
            postgresql_where=ACTIVE_SANDBOX_CONNECTION,
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    provider: Mapped[str]
    connected_account_id: Mapped[str] = mapped_column(unique=True)
    trigger_id: Mapped[str | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(default=MailAccountStatus.INITIATED)
    mode: Mapped[str | None] = mapped_column(nullable=True)
    phone_number: Mapped[str | None] = mapped_column(nullable=True)
    external_ref: Mapped[str | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class InboxEmail(ProductBase):
    __tablename__ = "inbox_emails"
    __table_args__ = (UniqueConstraint("provider", "external_message_id"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    connection_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("mailbox_connections.id"), nullable=True
    )
    provider: Mapped[str]
    external_message_id: Mapped[str]
    sender: Mapped[str] = mapped_column(default="")
    subject: Mapped[str] = mapped_column(default="")
    body: Mapped[str] = mapped_column(Text, default="")
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(default=InboxEmailStatus.RECEIVED, index=True)
    violations: Mapped[list] = mapped_column(JSONB, default=list)
    file_id: Mapped[UUID | None] = mapped_column(ForeignKey("files.id"), nullable=True)
    run_id: Mapped[UUID | None] = mapped_column(ForeignKey("agent_runs.id"), nullable=True)
    error: Mapped[str | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
