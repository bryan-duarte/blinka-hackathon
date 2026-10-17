from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from contracts.bills import (
    BillClaim,
    BillFields,
    BillRecord,
    BillSourceIntake,
    BillSourceRecord,
    BillStatus,
    BillSummary,
    SourceRegistration,
)

if TYPE_CHECKING:
    from modules.bills.service import BillsService


class BillsClient:
    def __init__(self, service: "BillsService") -> None:
        self._service = service

    async def register_source(self, intake: BillSourceIntake) -> SourceRegistration:
        return await self._service.register_source(intake)

    async def get_source(self, owner_id: UUID, source_id: UUID) -> BillSourceRecord:
        return await self._service.get_source(owner_id, source_id)

    async def list_sources_for_bill(self, owner_id: UUID, bill_id: UUID) -> list[BillSourceRecord]:
        return await self._service.list_sources_for_bill(owner_id, bill_id)

    async def claim_bill(
        self, owner_id: UUID, source: BillSourceRecord, fields: BillFields
    ) -> BillClaim:
        return await self._service.claim_bill(owner_id, source, fields)

    async def transition(
        self,
        owner_id: UUID,
        bill_id: UUID,
        expected: BillStatus | tuple[BillStatus, ...],
        target: BillStatus,
    ) -> BillRecord:
        return await self._service.transition(owner_id, bill_id, expected, target)

    async def get_bill(self, owner_id: UUID, bill_id: UUID) -> BillRecord:
        return await self._service.get_bill(owner_id, bill_id)

    async def list_bills(self, owner_id: UUID, status: BillStatus | None) -> list[BillRecord]:
        return await self._service.list_bills(owner_id, status)

    async def recent_canonical_bills(
        self, owner_id: UUID, payee_id: UUID, since: datetime, exclude_bill_id: UUID
    ) -> list[BillSummary]:
        return await self._service.recent_canonical_bills(
            owner_id, payee_id, since, exclude_bill_id
        )

    async def stuck_bills(self, statuses: tuple[BillStatus, ...]) -> list[BillRecord]:
        return await self._service.stuck_bills(statuses)
