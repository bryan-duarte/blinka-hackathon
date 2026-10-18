from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Index, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import ProductBase

CURRENCY_CODE_LENGTH = 3
FX_SOURCE_LENGTH = 24
USD_PER_UNIT = Numeric(20, 10)
FX_RATE_CONSTRAINT = "uq_fx_rates_currency_date_source"


class FxRateRow(ProductBase):
    __tablename__ = "fx_rates"
    __table_args__ = (
        UniqueConstraint("quote_currency", "rate_date", "source", name=FX_RATE_CONSTRAINT),
        Index("ix_fx_rates_currency_date", "quote_currency", "rate_date"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    quote_currency: Mapped[str] = mapped_column(String(CURRENCY_CODE_LENGTH))
    rate_date: Mapped[date]
    usd_per_unit: Mapped[Decimal] = mapped_column(USD_PER_UNIT)
    source: Mapped[str] = mapped_column(String(FX_SOURCE_LENGTH))
    fetched_at: Mapped[datetime] = mapped_column(server_default=func.now())
