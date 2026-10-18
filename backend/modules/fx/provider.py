from datetime import UTC, date, datetime
from decimal import Decimal, DivisionByZero, InvalidOperation
from typing import Protocol

import httpx
from pydantic import ValidationError

from contracts.fx import LatestRatesResponse
from core.config import FxSettings
from modules.fx.errors import FxProviderError

USD_PER_UNIT_PRECISION = Decimal("0.0000000001")
ONE_UNIT = Decimal("1")


class LatestRatesProvider(Protocol):
    async def fetch_latest(self) -> tuple[date, dict[str, Decimal]]: ...


class OpenErApiProvider:
    def __init__(self, settings: FxSettings) -> None:
        self._settings = settings

    async def fetch_latest(self) -> tuple[date, dict[str, Decimal]]:
        try:
            async with httpx.AsyncClient(timeout=self._settings.timeout_seconds) as client:
                response = await client.get(self._settings.latest_url)
                response.raise_for_status()
            latest = LatestRatesResponse.model_validate_json(response.content)
        except (httpx.HTTPError, ValidationError) as error:
            raise FxProviderError from error
        rate_date = datetime.fromtimestamp(latest.time_last_update_unix, UTC).date()
        return rate_date, _usd_per_unit(latest.rates)


def _usd_per_unit(units_per_usd: dict[str, Decimal]) -> dict[str, Decimal]:
    usd_per_unit = {}
    for currency, units in units_per_usd.items():
        try:
            usd_per_unit[currency.upper()] = (ONE_UNIT / units).quantize(USD_PER_UNIT_PRECISION)
        except (DivisionByZero, InvalidOperation):
            continue
    return usd_per_unit
