from fastapi import APIRouter, Depends

from api.deps import get_current_user
from api.routers import (
    accountability,
    auth,
    bills,
    demo,
    files,
    inbox,
    payment_policy,
    payments,
    webhooks,
)

api_router = APIRouter()


@api_router.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok"}


api_router.include_router(auth.auth_router)
api_router.include_router(demo.demo_router, dependencies=[Depends(get_current_user)])
api_router.include_router(accountability.ledger_router, dependencies=[Depends(get_current_user)])
api_router.include_router(accountability.runs_router, dependencies=[Depends(get_current_user)])
api_router.include_router(webhooks.webhooks_router)
api_router.include_router(files.files_router, dependencies=[Depends(get_current_user)])
api_router.include_router(payments.payments_router, dependencies=[Depends(get_current_user)])
api_router.include_router(inbox.inbox_router, dependencies=[Depends(get_current_user)])
api_router.include_router(
    payment_policy.payment_policy_router, dependencies=[Depends(get_current_user)]
)
api_router.include_router(bills.bills_router, dependencies=[Depends(get_current_user)])
api_router.include_router(bills.budgets_router, dependencies=[Depends(get_current_user)])
