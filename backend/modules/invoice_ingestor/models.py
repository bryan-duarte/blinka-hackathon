from uuid import UUID

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import ProductBase


class InvoiceRecord(ProductBase):
    __tablename__ = "invoices"

    file_id: Mapped[UUID] = mapped_column(ForeignKey("files.id"), unique=True, primary_key=True)
    data: Mapped[dict] = mapped_column(JSONB, default=dict)
