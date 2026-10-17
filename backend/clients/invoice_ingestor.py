from typing import TYPE_CHECKING

from contracts.auth import CurrentUser
from contracts.bills import BillDocument
from contracts.payment_candidates import BillClassification, PaymentCandidateBase
from contracts.payment_policy import PayeeKind

if TYPE_CHECKING:
    from modules.invoice_ingestor.service import InvoiceIngestorService


class InvoiceIngestorClient:
    def __init__(self, service: "InvoiceIngestorService") -> None:
        self._service = service

    async def classify(self, owner: CurrentUser, document: BillDocument) -> BillClassification:
        return await self._service.classify(owner, document)

    async def extract_candidate(
        self, owner: CurrentUser, document: BillDocument, kind: PayeeKind
    ) -> PaymentCandidateBase:
        return await self._service.extract_candidate(owner, document, kind)
