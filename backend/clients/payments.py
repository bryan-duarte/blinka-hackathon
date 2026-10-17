from typing import TYPE_CHECKING
from uuid import UUID

from contracts.auth import CurrentUser
from contracts.payments import PaymentRunAccepted, PaymentRunStatus, PaymentRunTrigger

if TYPE_CHECKING:
    from modules.payments.service import PaymentsService


class PaymentsClient:
    def __init__(self, service: "PaymentsService") -> None:
        self._service = service

    async def start_run(self, trigger: PaymentRunTrigger, owner: CurrentUser) -> PaymentRunAccepted:
        return await self._service.start_run(trigger, owner)

    async def get_run(self, run_id: UUID, owner: CurrentUser) -> PaymentRunStatus:
        return await self._service.get_run(run_id, owner)

    async def fail_unfinished(self, reason: str) -> None:
        await self._service.fail_unfinished(reason)

    async def shutdown_runs(self) -> None:
        await self._service.shutdown()
