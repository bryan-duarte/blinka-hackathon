from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import Delete, Update, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.bills.models import BillRow, BillSourceRow
from modules.files.models import FileRecord
from modules.inbox.models import InboxEmail
from modules.payment_policy.models import (
    BlacklistEntryRow,
    PayeeIdentifierRow,
    PayeeRow,
    PaymentPolicyRow,
)
from modules.payments.models import (
    AgentRun,
    AgentRunEvent,
    AgentRunFileRow,
    BudgetCounterRow,
    PaymentDecisionRow,
    PaymentRow,
)


@dataclass(frozen=True)
class OwnerRefs:
    run_ids: list[UUID]
    stored_file_count: int


class DemoResetRepository:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    async def collect_owner_refs(self, owner_id: UUID) -> OwnerRefs:
        runs_statement = select(AgentRun.id).where(AgentRun.owner_id == owner_id)
        files_statement = select(func.count(FileRecord.id)).where(FileRecord.owner_id == owner_id)
        async with self._sessionmaker() as session:
            run_ids = list((await session.execute(runs_statement)).scalars().all())
            stored_file_count = (await session.execute(files_statement)).scalar_one()
        return OwnerRefs(run_ids=run_ids, stored_file_count=stored_file_count)

    async def purge_owner(self, owner_id: UUID) -> dict[str, int]:
        deleted_rows: dict[str, int] = {}
        async with self._sessionmaker() as session, session.begin():
            for table_name, statement in _purge_statements(owner_id):
                outcome = await session.execute(statement)
                if isinstance(statement, Delete):
                    deleted_rows[table_name] = deleted_rows.get(table_name, 0) + outcome.rowcount
        return deleted_rows


def _purge_statements(owner_id: UUID) -> list[tuple[str, Delete | Update]]:
    owner_runs = select(AgentRun.id).where(AgentRun.owner_id == owner_id)
    owner_sources = select(BillSourceRow.id).where(BillSourceRow.owner_id == owner_id)
    owner_bills = select(BillRow.id).where(BillRow.owner_id == owner_id)
    return [
        ("agent_run_events", delete(AgentRunEvent).where(AgentRunEvent.run_id.in_(owner_runs))),
        (
            "agent_run_files",
            delete(AgentRunFileRow).where(
                or_(
                    AgentRunFileRow.run_id.in_(owner_runs),
                    AgentRunFileRow.bill_source_id.in_(owner_sources),
                )
            ),
        ),
        (
            "payment_decisions",
            delete(PaymentDecisionRow).where(PaymentDecisionRow.bill_id.in_(owner_bills)),
        ),
        ("payments", delete(PaymentRow).where(PaymentRow.owner_id == owner_id)),
        ("budget_counters", delete(BudgetCounterRow).where(BudgetCounterRow.owner_id == owner_id)),
        (
            "inbox_emails",
            update(InboxEmail)
            .where(InboxEmail.owner_id == owner_id)
            .values(run_id=None, file_id=None),
        ),
        (
            "bill_sources",
            update(BillSourceRow).where(BillSourceRow.owner_id == owner_id).values(bill_id=None),
        ),
        ("agent_runs", delete(AgentRun).where(AgentRun.owner_id == owner_id)),
        ("bill_sources", delete(BillSourceRow).where(BillSourceRow.owner_id == owner_id)),
        ("inbox_emails", delete(InboxEmail).where(InboxEmail.owner_id == owner_id)),
        (
            "bills",
            delete(BillRow).where(
                BillRow.owner_id == owner_id, BillRow.duplicate_of_bill_id.is_not(None)
            ),
        ),
        ("bills", delete(BillRow).where(BillRow.owner_id == owner_id)),
        ("files", delete(FileRecord).where(FileRecord.owner_id == owner_id)),
        (
            "blacklist_entries",
            delete(BlacklistEntryRow).where(BlacklistEntryRow.owner_id == owner_id),
        ),
        (
            "payee_identifiers",
            delete(PayeeIdentifierRow).where(PayeeIdentifierRow.owner_id == owner_id),
        ),
        ("payees", delete(PayeeRow).where(PayeeRow.owner_id == owner_id)),
        (
            "payment_policies",
            delete(PaymentPolicyRow).where(PaymentPolicyRow.owner_id == owner_id),
        ),
    ]
