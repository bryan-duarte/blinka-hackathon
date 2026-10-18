from typing import TYPE_CHECKING
from uuid import UUID

from contracts.auth import CurrentUser
from contracts.bills import BillSourceType, BillStatus
from contracts.payments import (
    BillDecisionView,
    BillDetail,
    BudgetUsageView,
    PaymentRunAccepted,
    PaymentRunStatus,
    PaymentRunTrigger,
    ReviewActionRequest,
    RunTraceView,
)

if TYPE_CHECKING:
    from modules.payments.service import PaymentsService


class PaymentsClient:
    def __init__(self, service: "PaymentsService") -> None:
        self._service = service

    async def start_run(self, trigger: PaymentRunTrigger, owner: CurrentUser) -> PaymentRunAccepted:
        return await self._service.start_run(trigger, owner)

    async def start_file_run(
        self,
        owner: CurrentUser,
        file_id: UUID,
        source_type: BillSourceType,
        source_ref: str,
        body_text: str = "",
    ) -> PaymentRunAccepted:
        return await self._service.start_file_run(
            owner, file_id, source_type, source_ref, body_text
        )

    async def get_run(self, run_id: UUID, owner: CurrentUser) -> PaymentRunStatus:
        return await self._service.get_run(run_id, owner)

    async def list_bills(
        self, owner: CurrentUser, status: BillStatus | None
    ) -> list[BillDecisionView]:
        return await self._service.list_bills(owner, status)

    async def get_bill(self, owner: CurrentUser, bill_id: UUID) -> BillDetail:
        return await self._service.get_bill(owner, bill_id)

    async def approve(
        self, owner: CurrentUser, bill_id: UUID, request: ReviewActionRequest
    ) -> BillDecisionView:
        return await self._service.approve(owner, bill_id, request)

    async def reject(
        self, owner: CurrentUser, bill_id: UUID, request: ReviewActionRequest
    ) -> BillDecisionView:
        return await self._service.reject(owner, bill_id, request)

    async def budget_usage(self, owner: CurrentUser, period: str | None) -> list[BudgetUsageView]:
        return await self._service.budget_usage(owner, period)

    async def recover_unfinished_payments(self) -> None:
        await self._service.recover_unfinished_payments()

    async def fail_unfinished(self, reason: str) -> None:
        await self._service.fail_unfinished(reason)

    async def run_trace(self, owner: CurrentUser, run_id: UUID) -> RunTraceView:
        return await self._service.run_trace(owner, run_id)

    async def cancel_owner(self, owner_id: UUID) -> int:
        return await self._service.cancel_owner(owner_id)

    async def purge_run_threads(self, run_ids: list[UUID]) -> int:
        return await self._service.purge_run_threads(run_ids)

    async def shutdown_runs(self) -> None:
        await self._service.shutdown()
