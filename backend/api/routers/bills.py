from uuid import UUID

from fastapi import APIRouter, Query

from api.deps import ClientsDep, CurrentUserDep
from contracts.bills import BillStatus
from contracts.payments import BillDecisionView, BillDetail, BudgetUsageView, ReviewActionRequest

PERIOD_PATTERN = r"^\d{4}-\d{2}$"

bills_router = APIRouter(prefix="/bills", tags=["bills"])
budgets_router = APIRouter(prefix="/budgets", tags=["bills"])


@bills_router.get("", response_model=list[BillDecisionView])
async def list_bills(
    user: CurrentUserDep, clients: ClientsDep, status: BillStatus | None = None
) -> list[BillDecisionView]:
    return await clients.payments.list_bills(user, status)


@bills_router.get("/{bill_id}", response_model=BillDetail)
async def get_bill(bill_id: UUID, user: CurrentUserDep, clients: ClientsDep) -> BillDetail:
    return await clients.payments.get_bill(user, bill_id)


@bills_router.post("/{bill_id}/approve", response_model=BillDecisionView)
async def approve_bill(
    bill_id: UUID, request: ReviewActionRequest, user: CurrentUserDep, clients: ClientsDep
) -> BillDecisionView:
    return await clients.payments.approve(user, bill_id, request)


@bills_router.post("/{bill_id}/reject", response_model=BillDecisionView)
async def reject_bill(
    bill_id: UUID, request: ReviewActionRequest, user: CurrentUserDep, clients: ClientsDep
) -> BillDecisionView:
    return await clients.payments.reject(user, bill_id, request)


@budgets_router.get("", response_model=list[BudgetUsageView])
async def budget_usage(
    user: CurrentUserDep,
    clients: ClientsDep,
    period: str | None = Query(default=None, pattern=PERIOD_PATTERN),
) -> list[BudgetUsageView]:
    return await clients.payments.budget_usage(user, period)
