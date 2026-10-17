from datetime import datetime
from uuid import UUID

from contracts.bills import (
    BillClaim,
    BillFields,
    BillRecord,
    BillSourceIntake,
    BillSourceRecord,
    BillSourceType,
    BillStatus,
    BillSummary,
    SourceRegistration,
)
from core.logging_config import get_logger
from modules.bills.errors import (
    BillMissingError,
    BillSourceMissingError,
    BillStateConflictError,
    InvalidBillTransitionError,
)
from modules.bills.hashing import bill_fingerprint, normalize_invoice_number, sha256_hex
from modules.bills.repository import BillsRepository

logger = get_logger(__name__)

ALLOWED_TRANSITIONS: dict[BillStatus, frozenset[BillStatus]] = {
    BillStatus.DECIDING: frozenset({BillStatus.PAID, BillStatus.HELD, BillStatus.REVIEW}),
    BillStatus.REVIEW: frozenset({BillStatus.APPROVING, BillStatus.REJECTED}),
    BillStatus.APPROVING: frozenset({BillStatus.PAID, BillStatus.HELD, BillStatus.REVIEW}),
}
WHOLE_CONTENT_HASHED_SOURCES = frozenset({BillSourceType.UPLOAD, BillSourceType.CHAT})
CLAIM_ATTEMPTS = 2


class BillsService:
    def __init__(self, repository: BillsRepository) -> None:
        self._repository = repository

    async def register_source(self, intake: BillSourceIntake) -> SourceRegistration:
        content_parts = [intake.body_text.encode()]
        if intake.attachment_sha256:
            content_parts.append(intake.attachment_sha256.encode())
        registration = await self._repository.register_source(intake, sha256_hex(*content_parts))
        if not registration.is_new:
            logger.info(
                "bill_source_duplicate",
                source_id=registration.source.source_id,
                source_type=intake.source_type,
            )
        return registration

    async def get_source(self, owner_id: UUID, source_id: UUID) -> BillSourceRecord:
        source = await self._repository.get_source(owner_id, source_id)
        if source is None:
            raise BillSourceMissingError
        return source

    async def list_sources_for_bill(self, owner_id: UUID, bill_id: UUID) -> list[BillSourceRecord]:
        return await self._repository.list_sources_for_bill(owner_id, bill_id)

    async def claim_bill(
        self, owner_id: UUID, source: BillSourceRecord, fields: BillFields
    ) -> BillClaim:
        invoice_number = normalize_invoice_number(fields.invoice_number)
        normalized_fields = fields.model_copy(update={"invoice_number": invoice_number})
        payee_key = str(fields.payee_id) if fields.payee_id else fields.normalized_payee_name
        fingerprint = bill_fingerprint(
            owner_id, payee_key, invoice_number, fields.due_date, fields.amount, fields.currency
        )
        document_sha256 = _document_sha256(source)
        claim = None
        for _ in range(CLAIM_ATTEMPTS):
            claim = await self._repository.claim_bill(
                owner_id, source.source_id, normalized_fields, document_sha256, fingerprint
            )
            if claim is not None:
                break
        if claim is None:
            raise BillStateConflictError
        if claim.duplicate_of is not None:
            logger.info(
                "bill_duplicate_detected",
                bill_id=claim.bill.bill_id,
                original_bill_id=claim.duplicate_of.bill_id,
            )
        return claim

    async def transition(
        self,
        owner_id: UUID,
        bill_id: UUID,
        expected: BillStatus | tuple[BillStatus, ...],
        target: BillStatus,
    ) -> BillRecord:
        expected_statuses = expected if isinstance(expected, tuple) else (expected,)
        is_allowed = all(
            target in ALLOWED_TRANSITIONS.get(status, frozenset()) for status in expected_statuses
        )
        if not is_allowed:
            raise InvalidBillTransitionError
        bill = await self._repository.transition(owner_id, bill_id, expected_statuses, target)
        if bill is None:
            raise BillStateConflictError
        return bill

    async def get_bill(self, owner_id: UUID, bill_id: UUID) -> BillRecord:
        bill = await self._repository.get_bill(owner_id, bill_id)
        if bill is None:
            raise BillMissingError
        return bill

    async def list_bills(self, owner_id: UUID, status: BillStatus | None) -> list[BillRecord]:
        return await self._repository.list_bills(owner_id, status)

    async def recent_canonical_bills(
        self, owner_id: UUID, payee_id: UUID, since: datetime, exclude_bill_id: UUID
    ) -> list[BillSummary]:
        return await self._repository.recent_canonical_bills(
            owner_id, payee_id, since, exclude_bill_id
        )

    async def stuck_bills(self, statuses: tuple[BillStatus, ...]) -> list[BillRecord]:
        return await self._repository.stuck_bills(statuses)


def _document_sha256(source: BillSourceRecord) -> str | None:
    if source.attachment_sha256:
        return source.attachment_sha256
    if source.source_type in WHOLE_CONTENT_HASHED_SOURCES:
        return source.content_sha256
    return None
