from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response

from api.deps import ClientsDep, CurrentUserDep
from contracts.accountability import (
    PERIOD_PATTERN,
    LedgerEntryView,
    LedgerFilters,
    LedgerSummaryView,
    RunListItemView,
)
from contracts.payments import RunStatus

CSV_MEDIA_TYPE = "text/csv; charset=utf-8"
ALL_PERIODS_LABEL = "all"
DEFAULT_SUMMARY_MONTHS = 4
MAX_SUMMARY_MONTHS = 12
DEFAULT_RUN_LIMIT = 100
MAX_RUN_LIMIT = 300

ledger_router = APIRouter(prefix="/ledger", tags=["ledger"])
runs_router = APIRouter(prefix="/runs", tags=["runs"])

LedgerFiltersDep = Annotated[LedgerFilters, Query()]


@ledger_router.get("/entries", response_model=list[LedgerEntryView])
async def list_ledger_entries(
    filters: LedgerFiltersDep, user: CurrentUserDep, clients: ClientsDep
) -> list[LedgerEntryView]:
    return await clients.accountability.ledger_entries(user, filters)


@ledger_router.get("/summary", response_model=LedgerSummaryView)
async def get_ledger_summary(
    user: CurrentUserDep,
    clients: ClientsDep,
    period: Annotated[str | None, Query(pattern=PERIOD_PATTERN)] = None,
    months: Annotated[int, Query(ge=1, le=MAX_SUMMARY_MONTHS)] = DEFAULT_SUMMARY_MONTHS,
) -> LedgerSummaryView:
    return await clients.accountability.summary(user, period, months)


@ledger_router.get("/export.csv")
async def export_ledger_csv(
    filters: LedgerFiltersDep, user: CurrentUserDep, clients: ClientsDep
) -> Response:
    csv_content = await clients.accountability.export_csv(user, filters)
    filename = f"agent-ledger-{filters.period or ALL_PERIODS_LABEL}.csv"
    return Response(
        content=csv_content,
        media_type=CSV_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@runs_router.get("", response_model=list[RunListItemView])
async def list_runs(
    user: CurrentUserDep,
    clients: ClientsDep,
    status: RunStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_RUN_LIMIT)] = DEFAULT_RUN_LIMIT,
) -> list[RunListItemView]:
    return await clients.accountability.list_runs(user, status, limit)


@runs_router.get("/{run_id}", response_model=RunListItemView)
async def get_run(run_id: UUID, user: CurrentUserDep, clients: ClientsDep) -> RunListItemView:
    return await clients.accountability.get_run(user, run_id)
