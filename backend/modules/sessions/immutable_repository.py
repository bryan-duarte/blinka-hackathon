from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from contracts.sessions import ExecutionRecord
from modules.sessions.models import SessionExecution

EXECUTION_LOG_LIMIT = 100


class SessionsImmutableRepository:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    async def append(
        self, session_id: UUID, agent: str, input_summary: str, output_summary: str
    ) -> UUID:
        execution = SessionExecution(
            session_id=session_id,
            agent=agent,
            input_summary=input_summary,
            output_summary=output_summary,
        )
        async with self._sessionmaker() as session:
            session.add(execution)
            await session.commit()
            return execution.id

    async def get(self, execution_id: UUID) -> ExecutionRecord | None:
        statement = select(SessionExecution).where(SessionExecution.id == execution_id)
        async with self._sessionmaker() as session:
            result = await session.execute(statement)
            execution = result.scalar_one_or_none()
        if execution is None:
            return None
        return _to_execution_record(execution)

    async def list_by_session(
        self, session_id: UUID, limit: int = EXECUTION_LOG_LIMIT
    ) -> list[ExecutionRecord]:
        statement = (
            select(SessionExecution)
            .where(SessionExecution.session_id == session_id)
            .order_by(SessionExecution.occurred_at.asc())
            .limit(limit)
        )
        async with self._sessionmaker() as session:
            result = await session.execute(statement)
            executions = result.scalars().all()
        return [_to_execution_record(execution) for execution in executions]


def _to_execution_record(execution: SessionExecution) -> ExecutionRecord:
    return ExecutionRecord(
        execution_id=execution.id,
        session_id=execution.session_id,
        agent=execution.agent,
        input_summary=execution.input_summary,
        output_summary=execution.output_summary,
        occurred_at=execution.occurred_at,
    )
