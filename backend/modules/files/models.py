from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from contracts.files import FileParseStatus, FileScanStatus
from core.db.base import ProductBase

SCAN_STATUS_LENGTH = 16


class FileRecord(ProductBase):
    __tablename__ = "files"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    filename: Mapped[str]
    mime: Mapped[str]
    size_bytes: Mapped[int]
    storage_key: Mapped[str]
    parse_status: Mapped[str] = mapped_column(default=FileParseStatus.PENDING)
    scan_status: Mapped[str] = mapped_column(
        String(SCAN_STATUS_LENGTH),
        default=FileScanStatus.PENDING,
        server_default=FileScanStatus.PENDING.value,
    )
    scanned_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
