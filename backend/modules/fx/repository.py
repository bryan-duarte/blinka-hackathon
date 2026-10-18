from datetime import date
from decimal import Decimal

from sqlalchemy import Select, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from contracts.fx import FxQuote, FxSource
from modules.fx.models import FX_RATE_CONSTRAINT, FxRateRow


class FxRepository:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    async def latest_live_since(self, currency: str, since: date) -> FxQuote | None:
        statement = _newest_rate_since(currency, since).where(
            FxRateRow.source == FxSource.OPEN_ER_API
        )
        return await self._one_quote(statement)

    async def latest_stored_since(self, currency: str, since: date) -> FxQuote | None:
        statement = _newest_rate_since(currency, since).where(
            FxRateRow.source != FxSource.STATIC_FALLBACK
        )
        return await self._one_quote(statement)

    async def store_rates(
        self, rate_date: date, usd_per_unit_by_currency: dict[str, Decimal], source: FxSource
    ) -> None:
        if not usd_per_unit_by_currency:
            return
        statement = (
            insert(FxRateRow)
            .values(
                [
                    {
                        "quote_currency": currency,
                        "rate_date": rate_date,
                        "usd_per_unit": usd_per_unit,
                        "source": source,
                    }
                    for currency, usd_per_unit in usd_per_unit_by_currency.items()
                ]
            )
            .on_conflict_do_nothing(constraint=FX_RATE_CONSTRAINT)
        )
        async with self._sessionmaker() as session, session.begin():
            await session.execute(statement)

    async def _one_quote(self, statement: Select[tuple[FxRateRow]]) -> FxQuote | None:
        async with self._sessionmaker() as session:
            rate = (await session.execute(statement)).scalars().first()
        if rate is None:
            return None
        return FxQuote(
            currency=rate.quote_currency,
            usd_per_unit=rate.usd_per_unit,
            rate_date=rate.rate_date,
            source=FxSource(rate.source),
        )


def _newest_rate_since(currency: str, since: date) -> Select[tuple[FxRateRow]]:
    return (
        select(FxRateRow)
        .where(FxRateRow.quote_currency == currency, FxRateRow.rate_date >= since)
        .order_by(FxRateRow.rate_date.desc())
        .limit(1)
    )
