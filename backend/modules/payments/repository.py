from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from contracts.payments import PaymentRunEvent, PaymentRunRecord, RunStatus
from modules.payments.models import AgentRun, AgentRunEvent

ACTIVE_STATUSES = (RunStatus.PENDING, RunStatus.RUNNING)
RUN_EVENT_LIST_LIMIT = 100


class RunsRepository:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    async def insert_run(
        self,
        agent: str,
        owner_id: UUID,
        file_id: UUID | None,
        session_id: UUID | None,
    ) -> UUID:
        run = AgentRun(agent=agent, owner_id=owner_id, file_id=file_id, session_id=session_id)
        async with self._sessionmaker() as session:
            session.add(run)
            await session.commit()
            return run.id

    async def get_run(self, run_id: UUID, owner_id: UUID) -> PaymentRunRecord | None:
        statement = select(AgentRun).where(AgentRun.id == run_id, AgentRun.owner_id == owner_id)
        async with self._sessionmaker() as session:
            result = await session.execute(statement)
            run = result.scalar_one_or_none()
        if run is None:
            return None
        return PaymentRunRecord(run_id=run.id, status=RunStatus(run.status), error=run.error)

    async def update_status(
        self, run_id: UUID, status: RunStatus, error: str | None = None
    ) -> None:
        changed_columns = {"status": status, "updated_at": func.now()}
        if error is not None:
            changed_columns["error"] = error
        statement = update(AgentRun).where(AgentRun.id == run_id).values(**changed_columns)
        async with self._sessionmaker() as session:
            await session.execute(statement)
            await session.commit()

    async def insert_event(self, run_id: UUID, step: str, payload: dict) -> None:
        event = AgentRunEvent(run_id=run_id, step=step, payload=payload)
        async with self._sessionmaker() as session:
            session.add(event)
            await session.commit()

    async def list_events(
        self, run_id: UUID, limit: int = RUN_EVENT_LIST_LIMIT
    ) -> list[PaymentRunEvent]:
        statement = (
            select(AgentRunEvent)
            .where(AgentRunEvent.run_id == run_id)
            .order_by(AgentRunEvent.id.asc())
            .limit(limit)
        )
        async with self._sessionmaker() as session:
            result = await session.execute(statement)
            events = result.scalars().all()
        return [
            PaymentRunEvent(step=event.step, payload=event.payload, created_at=event.created_at)
            for event in events
        ]

    async def fail_unfinished(self, reason: str) -> int:
        statement = (
            update(AgentRun)
            .where(AgentRun.status.in_(ACTIVE_STATUSES))
            .values(status=RunStatus.FAILED, error=reason, updated_at=func.now())
            .returning(AgentRun.id)
        )
        async with self._sessionmaker() as session:
            result = await session.execute(statement)
            await session.commit()
            return len(result.scalars().all())
