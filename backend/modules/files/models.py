from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from contracts.files import FileParseStatus
from core.db.base import ProductBase


class FileRecord(ProductBase):
    __tablename__ = "files"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    filename: Mapped[str]
    mime: Mapped[str]
    size_bytes: Mapped[int]
    storage_key: Mapped[str]
    parse_status: Mapped[str] = mapped_column(default=FileParseStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
