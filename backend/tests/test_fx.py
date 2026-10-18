from datetime import date
from decimal import Decimal

from contracts.fx import FxQuote, FxSource
from core.config import FxSettings
from modules.fx import FxProviderError, FxService
from modules.fx.provider import _usd_per_unit

TODAY = date(2026, 10, 17)


class _FakeRepository:
    def __init__(self, stored: list[FxQuote] | None = None) -> None:
        self.stored = list(stored or [])

    async def latest_live_since(self, currency: str, since: date) -> FxQuote | None:
        return self._newest(currency, since, {FxSource.OPEN_ER_API})

    async def latest_stored_since(self, currency: str, since: date) -> FxQuote | None:
        return self._newest(currency, since, {FxSource.OPEN_ER_API, FxSource.CACHED})

    async def store_rates(
        self, rate_date: date, usd_per_unit_by_currency: dict[str, Decimal], source: FxSource
    ) -> None:
        self.stored.extend(
            FxQuote(currency=currency, usd_per_unit=rate, rate_date=rate_date, source=source)
            for currency, rate in usd_per_unit_by_currency.items()
        )

    def _newest(self, currency: str, since: date, sources: set[FxSource]) -> FxQuote | None:
        matching = [
            quote
            for quote in self.stored
            if quote.currency == currency and quote.rate_date >= since and quote.source in sources
        ]
        return max(matching, key=lambda quote: quote.rate_date, default=None)


class _FakeProvider:
    def __init__(self, rates: dict[str, Decimal] | None = None) -> None:
        self.rates = rates
        self.calls = 0

    async def fetch_latest(self) -> tuple[date, dict[str, Decimal]]:
        self.calls += 1
        if self.rates is None:
            raise FxProviderError
        return TODAY, self.rates


def _service(
    repository: _FakeRepository, provider: _FakeProvider, *, is_live: bool = True
) -> FxService:
    return FxService(repository, provider, FxSettings(live_enabled=is_live))


async def test_usd_is_identity_without_lookups():
    provider = _FakeProvider({"CLP": Decimal("0.001")})

    quote = await _service(_FakeRepository(), provider).quote("usd", TODAY)

    assert quote is not None
    assert quote.source is FxSource.IDENTITY
    assert quote.usd_per_unit == Decimal("1")
    assert provider.calls == 0


async def test_live_rate_is_fetched_once_and_then_read_from_storage():
    repository = _FakeRepository()
    provider = _FakeProvider({"CLP": Decimal("0.00105")})
    service = _service(repository, provider)

    first = await service.quote("CLP", TODAY)
    second = await service.quote("CLP", TODAY)

    assert first is not None and second is not None
    assert first.source is second.source is FxSource.OPEN_ER_API
    assert provider.calls == 1


async def test_failed_fetch_falls_back_to_cached_then_static_then_none():
    stale_live = FxQuote(
        currency="MXN",
        usd_per_unit=Decimal("0.054"),
        rate_date=date(2026, 10, 12),
        source=FxSource.OPEN_ER_API,
    )
    service = _service(_FakeRepository([stale_live]), _FakeProvider(None))

    cached = await service.quote("MXN", TODAY)
    static = await service.quote("CLF", TODAY)
    unknown = await service.quote("TRY", TODAY)

    assert cached is not None and cached.source is FxSource.CACHED
    assert cached.usd_per_unit == Decimal("0.054")
    assert static is not None and static.source is FxSource.STATIC_FALLBACK
    assert unknown is None


async def test_live_disabled_never_calls_the_provider():
    provider = _FakeProvider({"EUR": Decimal("1.1")})

    quote = await _service(_FakeRepository(), provider, is_live=False).quote("EUR", TODAY)

    assert quote is not None and quote.source is FxSource.STATIC_FALLBACK
    assert provider.calls == 0


def test_provider_rates_are_inverted_to_usd_per_unit():
    usd_per_unit = _usd_per_unit({"clp": Decimal("950"), "BAD": Decimal("0")})

    assert usd_per_unit == {"CLP": Decimal("0.0010526316")}


def test_quote_converts_with_cent_rounding():
    quote = FxQuote(
        currency="COP",
        usd_per_unit=Decimal("0.00025"),
        rate_date=TODAY,
        source=FxSource.SEED,
    )

    assert quote.convert(Decimal("8200000")) == Decimal("2050.00")
