from datetime import date
from typing import TYPE_CHECKING

from contracts.fx import FxQuote

if TYPE_CHECKING:
    from modules.fx.service import FxService


class FxClient:
    def __init__(self, service: "FxService") -> None:
        self._service = service

    async def quote(self, currency: str | None, on: date) -> FxQuote | None:
        return await self._service.quote(currency, on)
