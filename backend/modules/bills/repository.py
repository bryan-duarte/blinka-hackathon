from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

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
from contracts.payment_policy import PayeeKind, PaymentCategory
from modules.bills.models import IS_CANONICAL_BILL, SOURCE_CONSTRAINT, BillRow, BillSourceRow

BILL_LIST_LIMIT = 100


class BillsRepository:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    async def register_source(
        self, intake: BillSourceIntake, content_sha256: str
    ) -> SourceRegistration:
        statement = (
            insert(BillSourceRow)
            .values(
                owner_id=intake.owner_id,
                source_type=intake.source_type,
                source_ref=intake.source_ref,
                sender=intake.sender,
                body_text=intake.body_text,
                file_id=intake.file_id,
                content_sha256=content_sha256,
                attachment_sha256=intake.attachment_sha256,
                inbox_email_id=intake.inbox_email_id,
                received_at=intake.received_at,
            )
            .on_conflict_do_nothing(constraint=SOURCE_CONSTRAINT)
            .returning(BillSourceRow)
        )
        existing_statement = select(BillSourceRow).where(
            BillSourceRow.owner_id == intake.owner_id,
            BillSourceRow.source_type == intake.source_type,
            BillSourceRow.source_ref == intake.source_ref,
        )
        async with self._sessionmaker() as session, session.begin():
            inserted = (await session.execute(statement)).scalar_one_or_none()
            source = inserted or (await session.execute(existing_statement)).scalar_one()
        return SourceRegistration(source=_to_source(source), is_new=inserted is not None)

    async def get_source(self, owner_id: UUID, source_id: UUID) -> BillSourceRecord | None:
        statement = select(BillSourceRow).where(
            BillSourceRow.id == source_id, BillSourceRow.owner_id == owner_id
        )
        async with self._sessionmaker() as session:
            source = (await session.execute(statement)).scalar_one_or_none()
        if source is None:
            return None
        return _to_source(source)

    async def list_sources_for_bill(self, owner_id: UUID, bill_id: UUID) -> list[BillSourceRecord]:
        statement = (
            select(BillSourceRow)
            .where(BillSourceRow.owner_id == owner_id, BillSourceRow.bill_id == bill_id)
            .order_by(BillSourceRow.created_at.asc())
        )
        async with self._sessionmaker() as session:
            sources = (await session.execute(statement)).scalars().all()
        return [_to_source(source) for source in sources]

    async def claim_bill(
        self,
        owner_id: UUID,
        source_id: UUID,
        fields: BillFields,
        document_sha256: str | None,
        fingerprint: str | None,
    ) -> BillClaim | None:
        bill_columns = _bill_columns(owner_id, fields, document_sha256, fingerprint)
        canonical_insert = (
            insert(BillRow)
            .values(**bill_columns, status=BillStatus.DECIDING)
            .on_conflict_do_nothing()
            .returning(BillRow)
        )
        async with self._sessionmaker() as session, session.begin():
            bill = (await session.execute(canonical_insert)).scalar_one_or_none()
            original = None
            if bill is None:
                original = await _find_canonical(session, owner_id, document_sha256, fingerprint)
                if original is None:
                    return None
                duplicate_insert = (
                    insert(BillRow)
                    .values(
                        **bill_columns,
                        status=BillStatus.DUPLICATE,
                        duplicate_of_bill_id=original.id,
                    )
                    .returning(BillRow)
                )
                bill = (await session.execute(duplicate_insert)).scalar_one()
            await session.execute(
                update(BillSourceRow).where(BillSourceRow.id == source_id).values(bill_id=bill.id)
            )
        return BillClaim(bill=_to_bill(bill), duplicate_of=_to_bill(original) if original else None)

    async def transition(
        self,
        owner_id: UUID,
        bill_id: UUID,
        expected_statuses: tuple[BillStatus, ...],
        target: BillStatus,
    ) -> BillRecord | None:
        statement = (
            update(BillRow)
            .where(
                BillRow.id == bill_id,
                BillRow.owner_id == owner_id,
                BillRow.status.in_(expected_statuses),
            )
            .values(status=target, version=BillRow.version + 1, updated_at=func.now())
            .returning(BillRow)
        )
        async with self._sessionmaker() as session:
            bill = (await session.execute(statement)).scalar_one_or_none()
            await session.commit()
        if bill is None:
            return None
        return _to_bill(bill)

    async def get_bill(self, owner_id: UUID, bill_id: UUID) -> BillRecord | None:
        statement = select(BillRow).where(BillRow.id == bill_id, BillRow.owner_id == owner_id)
        bills = await self._bills(statement)
        return bills[0] if bills else None

    async def list_bills(
        self, owner_id: UUID, status: BillStatus | None, limit: int = BILL_LIST_LIMIT
    ) -> list[BillRecord]:
        statement = (
            select(BillRow)
            .where(BillRow.owner_id == owner_id)
            .order_by(BillRow.created_at.desc())
            .limit(limit)
        )
        if status is not None:
            statement = statement.where(BillRow.status == status)
        return await self._bills(statement)

    async def recent_canonical_bills(
        self, owner_id: UUID, payee_id: UUID, since: datetime, exclude_bill_id: UUID
    ) -> list[BillSummary]:
        statement = (
            select(
                BillRow.id,
                BillRow.invoice_number,
                BillRow.amount_usd,
                BillRow.due_date,
                BillRow.status,
                BillRow.created_at,
            )
            .where(
                BillRow.owner_id == owner_id,
                BillRow.payee_id == payee_id,
                BillRow.created_at >= since,
                BillRow.id != exclude_bill_id,
                IS_CANONICAL_BILL,
            )
            .order_by(BillRow.created_at.desc())
        )
        async with self._sessionmaker() as session:
            summaries = (await session.execute(statement)).all()
        return [
            BillSummary(
                bill_id=bill_id,
                invoice_number=invoice_number,
                amount_usd=amount_usd,
                due_date=due_date,
                status=BillStatus(status),
                created_at=created_at,
            )
            for bill_id, invoice_number, amount_usd, due_date, status, created_at in summaries
        ]

    async def stuck_bills(self, statuses: tuple[BillStatus, ...]) -> list[BillRecord]:
        return await self._bills(select(BillRow).where(BillRow.status.in_(statuses)))

    async def _bills(self, statement: Select[tuple[BillRow]]) -> list[BillRecord]:
        async with self._sessionmaker() as session:
            bills = (await session.execute(statement)).scalars().all()
        return [_to_bill(bill) for bill in bills]


async def _find_canonical(
    session: AsyncSession,
    owner_id: UUID,
    document_sha256: str | None,
    fingerprint: str | None,
) -> BillRow | None:
    same_bill_conditions = [
        column == key
        for column, key in (
            (BillRow.document_sha256, document_sha256),
            (BillRow.fingerprint, fingerprint),
        )
        if key is not None
    ]
    if not same_bill_conditions:
        return None
    statement = (
        select(BillRow)
        .where(BillRow.owner_id == owner_id, IS_CANONICAL_BILL, or_(*same_bill_conditions))
        .order_by(BillRow.created_at.asc())
        .limit(1)
    )
    return (await session.execute(statement)).scalar_one_or_none()


def _bill_columns(
    owner_id: UUID, fields: BillFields, document_sha256: str | None, fingerprint: str | None
) -> dict:
    return {
        "owner_id": owner_id,
        "kind": fields.kind,
        "payee_id": fields.payee_id,
        "payee_name": fields.payee_name,
        "invoice_number": fields.invoice_number,
        "amount": fields.amount,
        "currency": fields.currency,
        "amount_usd": fields.amount_usd,
        "category": fields.category,
        "due_date": fields.due_date,
        "candidate": fields.candidate,
        "document_sha256": document_sha256,
        "fingerprint": fingerprint,
    }


def _to_source(source: BillSourceRow) -> BillSourceRecord:
    return BillSourceRecord(
        source_id=source.id,
        owner_id=source.owner_id,
        source_type=BillSourceType(source.source_type),
        source_ref=source.source_ref,
        sender=source.sender,
        body_text=source.body_text,
        file_id=source.file_id,
        content_sha256=source.content_sha256,
        attachment_sha256=source.attachment_sha256,
        inbox_email_id=source.inbox_email_id,
        bill_id=source.bill_id,
        received_at=source.received_at,
        created_at=source.created_at,
    )


def _to_bill(bill: BillRow) -> BillRecord:
    return BillRecord(
        bill_id=bill.id,
        owner_id=bill.owner_id,
        kind=PayeeKind(bill.kind),
        payee_id=bill.payee_id,
        payee_name=bill.payee_name,
        invoice_number=bill.invoice_number,
        amount=bill.amount,
        currency=bill.currency,
        amount_usd=bill.amount_usd,
        category=PaymentCategory(bill.category) if bill.category else None,
        due_date=bill.due_date,
        candidate=dict(bill.candidate),
        document_sha256=bill.document_sha256,
        fingerprint=bill.fingerprint,
        duplicate_of_bill_id=bill.duplicate_of_bill_id,
        status=BillStatus(bill.status),
        version=bill.version,
        created_at=bill.created_at,
        updated_at=bill.updated_at,
    )
