from typing import TYPE_CHECKING
from uuid import UUID

from contracts.auth import CurrentUser
from contracts.invoices import InvoiceParseResult

if TYPE_CHECKING:
    from modules.invoice_ingestor.service import InvoiceIngestorService


class InvoiceIngestorClient:
    def __init__(self, service: "InvoiceIngestorService") -> None:
        self._service = service

    async def parse(self, owner: CurrentUser, file_id: UUID) -> InvoiceParseResult:
        return await self._service.parse(owner, file_id)
