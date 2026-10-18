import asyncio
from datetime import date, timedelta
from decimal import Decimal
from time import monotonic

from contracts.fx import USD, FxQuote, FxSource
from core.config import FxSettings
from core.logging_config import get_logger
from modules.fx.errors import FxProviderError
from modules.fx.provider import LatestRatesProvider
from modules.fx.repository import FxRepository
from modules.fx.static_rates import STATIC_RATES_REFERENCE_DATE, STATIC_USD_PER_UNIT

logger = get_logger(__name__)

PROVIDER_PUBLISH_LAG = timedelta(days=1)
LIVE_RETRY_COOLDOWN_SECONDS = 300
IDENTITY_RATE = Decimal("1")


class FxService:
    def __init__(
        self, repository: FxRepository, provider: LatestRatesProvider, settings: FxSettings
    ) -> None:
        self._repository = repository
        self._provider = provider
        self._settings = settings
        self._fetch_lock = asyncio.Lock()
        self._fetched_for: date | None = None
        self._last_failure_at: float | None = None

    async def quote(self, currency: str | None, on: date) -> FxQuote | None:
        if currency is None:
            return None
        code = currency.upper()
        if code == USD:
            return FxQuote(
                currency=USD, usd_per_unit=IDENTITY_RATE, rate_date=on, source=FxSource.IDENTITY
            )
        stored_live = await self._repository.latest_live_since(code, on - PROVIDER_PUBLISH_LAG)
        if stored_live is not None:
            return stored_live
        if self._settings.live_enabled:
            live = await self._fetch_live(code, on)
            if live is not None:
                return live
        return await self._fallback(code, on)

    async def _fetch_live(self, code: str, on: date) -> FxQuote | None:
        async with self._fetch_lock:
            stored_live = await self._repository.latest_live_since(code, on - PROVIDER_PUBLISH_LAG)
            if stored_live is not None:
                return stored_live
            if not self._may_fetch(on):
                return None
            try:
                rate_date, usd_per_unit_by_currency = await self._provider.fetch_latest()
            except FxProviderError:
                self._last_failure_at = monotonic()
                logger.warning("fx_live_fetch_failed", currency=code, exc_info=True)
                return None
            await self._repository.store_rates(
                rate_date, usd_per_unit_by_currency, FxSource.OPEN_ER_API
            )
            self._fetched_for = on
            logger.info(
                "fx_rates_fetched",
                rate_date=rate_date,
                currency_count=len(usd_per_unit_by_currency),
            )
        usd_per_unit = usd_per_unit_by_currency.get(code)
        if usd_per_unit is None:
            return None
        return FxQuote(
            currency=code,
            usd_per_unit=usd_per_unit,
            rate_date=rate_date,
            source=FxSource.OPEN_ER_API,
        )

    def _may_fetch(self, on: date) -> bool:
        already_fetched_today = self._fetched_for == on
        is_cooling_down = (
            self._last_failure_at is not None
            and monotonic() - self._last_failure_at < LIVE_RETRY_COOLDOWN_SECONDS
        )
        return not already_fetched_today and not is_cooling_down

    async def _fallback(self, code: str, on: date) -> FxQuote | None:
        stale_since = on - timedelta(days=self._settings.max_stale_days)
        stored = await self._repository.latest_stored_since(code, stale_since)
        if stored is not None:
            return stored.model_copy(update={"source": FxSource.CACHED})
        static_rate = STATIC_USD_PER_UNIT.get(code)
        if static_rate is None:
            logger.warning("fx_rate_unavailable", currency=code)
            return None
        return FxQuote(
            currency=code,
            usd_per_unit=static_rate,
            rate_date=STATIC_RATES_REFERENCE_DATE,
            source=FxSource.STATIC_FALLBACK,
        )
