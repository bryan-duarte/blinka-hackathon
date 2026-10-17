from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from contracts.sessions import SessionSummary
from modules.sessions.models import SessionRecord

SESSION_LIST_LIMIT = 50


class SessionsMutableRepository:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    async def create(self, owner_id: UUID, title: str = "") -> UUID:
        session_row = SessionRecord(owner_id=owner_id, title=title)
        async with self._sessionmaker() as session:
            session.add(session_row)
            await session.commit()
            return session_row.id

    async def get(self, session_id: UUID, owner_id: UUID) -> SessionSummary | None:
        statement = select(SessionRecord).where(
            SessionRecord.id == session_id, SessionRecord.owner_id == owner_id
        )
        async with self._sessionmaker() as session:
            result = await session.execute(statement)
            session_row = result.scalar_one_or_none()
        if session_row is None:
            return None
        return _to_summary(session_row)

    async def list_by_owner(
        self, owner_id: UUID, limit: int = SESSION_LIST_LIMIT
    ) -> list[SessionSummary]:
        statement = (
            select(SessionRecord)
            .where(SessionRecord.owner_id == owner_id)
            .order_by(SessionRecord.updated_at.desc())
            .limit(limit)
        )
        async with self._sessionmaker() as session:
            result = await session.execute(statement)
            session_rows = result.scalars().all()
        return [_to_summary(session_row) for session_row in session_rows]

    async def touch(self, session_id: UUID) -> None:
        statement = (
            update(SessionRecord)
            .where(SessionRecord.id == session_id)
            .values(updated_at=func.now())
        )
        async with self._sessionmaker() as session:
            await session.execute(statement)
            await session.commit()


def _to_summary(session_row: SessionRecord) -> SessionSummary:
    return SessionSummary(
        session_id=session_row.id, title=session_row.title, updated_at=session_row.updated_at
    )
