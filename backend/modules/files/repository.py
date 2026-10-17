from uuid import UUID

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from contracts.files import FileParseStatus, StoredFile
from modules.files.models import FileRecord


class FilesRepository:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    async def insert(
        self,
        owner_id: UUID,
        filename: str,
        mime: str,
        size_bytes: int,
        storage_key: str,
        parse_status: FileParseStatus,
    ) -> UUID:
        statement = (
            insert(FileRecord)
            .values(
                owner_id=owner_id,
                filename=filename,
                mime=mime,
                size_bytes=size_bytes,
                storage_key=storage_key,
                parse_status=parse_status,
            )
            .returning(FileRecord.id)
        )
        async with self._sessionmaker() as session:
            result = await session.execute(statement)
            await session.commit()
            return result.scalar_one()

    async def get(self, file_id: UUID, owner_id: UUID) -> StoredFile | None:
        statement = select(FileRecord).where(
            FileRecord.id == file_id, FileRecord.owner_id == owner_id
        )
        async with self._sessionmaker() as session:
            result = await session.execute(statement)
            record = result.scalar_one_or_none()
        if record is None:
            return None
        return _to_stored_file(record)

    async def set_parse_status(self, file_id: UUID, status: FileParseStatus) -> None:
        statement = update(FileRecord).where(FileRecord.id == file_id).values(parse_status=status)
        async with self._sessionmaker() as session:
            await session.execute(statement)
            await session.commit()


def _to_stored_file(record: FileRecord) -> StoredFile:
    return StoredFile(
        file_id=record.id,
        owner_id=record.owner_id,
        filename=record.filename,
        mime=record.mime,
        size_bytes=record.size_bytes,
        storage_key=record.storage_key,
        parse_status=FileParseStatus(record.parse_status),
    )
