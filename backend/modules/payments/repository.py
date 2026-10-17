from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from contracts.payments import PaymentRunEvent, PaymentRunRecord, RunStatus
from modules.payments.errors import RunTriggerError
from modules.payments.models import ACTIVE_RUN_STATUSES, AgentRun, AgentRunEvent

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
        bill_source_id: UUID,
    ) -> tuple[UUID, bool]:
        statement = (
            insert(AgentRun)
            .values(
                agent=agent,
                owner_id=owner_id,
                file_id=file_id,
                session_id=session_id,
                bill_source_id=bill_source_id,
                status=RunStatus.PENDING,
            )
            .on_conflict_do_nothing(
                index_elements=[AgentRun.bill_source_id],
                index_where=AgentRun.status.in_(ACTIVE_RUN_STATUSES),
            )
            .returning(AgentRun.id)
        )
        async with self._sessionmaker() as session:
            inserted_run_id = (await session.execute(statement)).scalar_one_or_none()
            await session.commit()
        if inserted_run_id is not None:
            return inserted_run_id, True
        active_run = await self.find_active_run(bill_source_id)
        if active_run is None:
            raise RunTriggerError
        return active_run.run_id, False

    async def find_active_run(self, bill_source_id: UUID) -> PaymentRunRecord | None:
        statement = select(AgentRun).where(
            AgentRun.bill_source_id == bill_source_id, AgentRun.status.in_(ACTIVE_RUN_STATUSES)
        )
        return await self._one_run(statement)

    async def latest_run_for_source(self, bill_source_id: UUID) -> PaymentRunRecord | None:
        statement = (
            select(AgentRun)
            .where(AgentRun.bill_source_id == bill_source_id)
            .order_by(AgentRun.created_at.desc())
            .limit(1)
        )
        return await self._one_run(statement)

    async def get_run(self, run_id: UUID, owner_id: UUID) -> PaymentRunRecord | None:
        statement = select(AgentRun).where(AgentRun.id == run_id, AgentRun.owner_id == owner_id)
        return await self._one_run(statement)

    async def set_run_bill(self, run_id: UUID, bill_id: UUID) -> None:
        statement = (
            update(AgentRun)
            .where(AgentRun.id == run_id)
            .values(bill_id=bill_id, updated_at=func.now())
        )
        async with self._sessionmaker() as session:
            await session.execute(statement)
            await session.commit()

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
            events = (await session.execute(statement)).scalars().all()
        return [
            PaymentRunEvent(step=event.step, payload=event.payload, created_at=event.created_at)
            for event in events
        ]

    async def fail_unfinished(self, reason: str) -> int:
        statement = (
            update(AgentRun)
            .where(AgentRun.status.in_(ACTIVE_RUN_STATUSES))
            .values(status=RunStatus.FAILED, error=reason, updated_at=func.now())
            .returning(AgentRun.id)
        )
        async with self._sessionmaker() as session:
            failed_run_ids = (await session.execute(statement)).scalars().all()
            await session.commit()
        return len(failed_run_ids)

    async def _one_run(self, statement) -> PaymentRunRecord | None:
        async with self._sessionmaker() as session:
            run = (await session.execute(statement)).scalar_one_or_none()
        if run is None:
            return None
        return PaymentRunRecord(
            run_id=run.id,
            status=RunStatus(run.status),
            error=run.error,
            bill_source_id=run.bill_source_id,
            bill_id=run.bill_id,
        )
