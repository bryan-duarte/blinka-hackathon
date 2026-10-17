from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from contracts.invoices import InvoiceData
from modules.invoice_ingestor.models import InvoiceRecord


class InvoicesRepository:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    async def upsert(self, file_id: UUID, invoice: InvoiceData) -> None:
        invoice_row = invoice.model_dump(mode="json")
        statement = (
            insert(InvoiceRecord)
            .values(file_id=file_id, data=invoice_row)
            .on_conflict_do_update(
                index_elements=[InvoiceRecord.file_id], set_={"data": invoice_row}
            )
        )
        async with self._sessionmaker() as session:
            await session.execute(statement)
            await session.commit()

    async def get(self, file_id: UUID) -> InvoiceData | None:
        statement = select(InvoiceRecord.data).where(InvoiceRecord.file_id == file_id)
        async with self._sessionmaker() as session:
            result = await session.execute(statement)
            invoice_row = result.scalar_one_or_none()
        if invoice_row is None:
            return None
        return InvoiceData.model_validate(invoice_row)
