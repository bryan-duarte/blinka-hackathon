from typing import TYPE_CHECKING
from uuid import UUID

from contracts.accountability import (
    LedgerEntryView,
    LedgerFilters,
    LedgerSummaryView,
    RunListItemView,
)
from contracts.auth import CurrentUser
from contracts.payments import RunStatus

if TYPE_CHECKING:
    from modules.accountability.service import AccountabilityService


class AccountabilityClient:
    def __init__(self, service: "AccountabilityService") -> None:
        self._service = service

    async def ledger_entries(
        self, owner: CurrentUser, filters: LedgerFilters
    ) -> list[LedgerEntryView]:
        return await self._service.ledger_entries(owner, filters)

    async def summary(
        self, owner: CurrentUser, period: str | None, months: int
    ) -> LedgerSummaryView:
        return await self._service.summary(owner, period, months)

    async def export_csv(self, owner: CurrentUser, filters: LedgerFilters) -> str:
        return await self._service.export_csv(owner, filters)

    async def get_run(self, owner: CurrentUser, run_id: UUID) -> RunListItemView:
        return await self._service.get_run(owner, run_id)

    async def list_runs(
        self, owner: CurrentUser, status: RunStatus | None, limit: int
    ) -> list[RunListItemView]:
        return await self._service.list_runs(owner, status, limit)
