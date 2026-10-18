from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict

from contracts._base import StrictModel

USD = "USD"
USD_CENTS = Decimal("0.01")


class FxSource(StrEnum):
    IDENTITY = "identity"
    OPEN_ER_API = "open_er_api"
    CACHED = "cached"
    STATIC_FALLBACK = "static_fallback"
    SEED = "seed"


class FxQuote(StrictModel):
    currency: str
    usd_per_unit: Decimal
    rate_date: date
    source: FxSource

    def convert(self, amount: Decimal) -> Decimal:
        return (amount * self.usd_per_unit).quantize(USD_CENTS, rounding=ROUND_HALF_UP)


class LatestRatesResponse(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    result: Literal["success"]
    time_last_update_unix: int
    rates: dict[str, Decimal]
