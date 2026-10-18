from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import RowMapping, Select, and_, exists, func, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from contracts.accountability import DecisionLedgerRow, InboxLedgerRow, RunListRow
from contracts.bills import BillSourceType, BillStatus
from contracts.fx import FxSource
from contracts.inbox import SOURCE_TYPE_BY_PROVIDER, InboxEmailStatus
from contracts.mail_gateway import MailProvider
from contracts.payment_policy import PayeeKind, PaymentCategory
from contracts.payments import DecisionActor, RunStatus, Verdict
from modules.bills.models import BillRow, BillSourceRow
from modules.inbox.models import InboxEmail
from modules.payment_policy.models import PayeeRow
from modules.payments.events import EXTRACTION_FAILED_STEP, TOOL_FINISHED_STEP
from modules.payments.models import AgentRun, AgentRunEvent, PaymentDecisionRow

LEDGER_ENTRY_LIMIT = 500
PERIOD_FORMAT = "YYYY-MM"
INBOX_ONLY_STATUSES = (
    InboxEmailStatus.BLOCKED,
    InboxEmailStatus.DUPLICATE,
    InboxEmailStatus.ERROR,
)
FINISHED_RUN_STATUSES = (RunStatus.COMPLETED, RunStatus.FAILED)


class AccountabilityRepository:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    async def decision_rows(
        self,
        owner_id: UUID,
        period: str | None,
        payee_id: UUID | None,
        currency: str | None,
        since: datetime | None,
        until: datetime | None,
    ) -> list[DecisionLedgerRow]:
        statement = _decision_statement(owner_id)
        if period is not None:
            statement = statement.where(
                func.to_char(PaymentDecisionRow.created_at, PERIOD_FORMAT) == period
            )
        if since is not None:
            statement = statement.where(PaymentDecisionRow.created_at >= since)
        if until is not None:
            statement = statement.where(PaymentDecisionRow.created_at < until)
        if payee_id is not None:
            statement = statement.where(BillRow.payee_id == payee_id)
        if currency is not None:
            statement = statement.where(BillRow.currency == currency)
        async with self._sessionmaker() as session:
            rows = (await session.execute(statement)).mappings().all()
        return [_to_decision_ledger_row(row) for row in rows]

    async def inbox_rows(
        self,
        owner_id: UUID,
        period: str | None,
        since: datetime | None,
        until: datetime | None,
    ) -> list[InboxLedgerRow]:
        occurred_at = func.coalesce(AgentRun.updated_at, InboxEmail.updated_at)
        has_extraction_failed = exists().where(
            AgentRunEvent.run_id == AgentRun.id, AgentRunEvent.step == EXTRACTION_FAILED_STEP
        )
        is_finished_without_bill = and_(
            InboxEmail.status == InboxEmailStatus.ANALYZING,
            AgentRun.status.in_(FINISHED_RUN_STATUSES),
        )
        statement = (
            select(
                InboxEmail.id.label("inbox_email_id"),
                occurred_at.label("occurred_at"),
                InboxEmail.status,
                InboxEmail.violations,
                InboxEmail.error,
                InboxEmail.subject,
                InboxEmail.provider,
                AgentRun.id.label("run_id"),
                AgentRun.status.label("run_status"),
                has_extraction_failed.label("has_extraction_failed"),
            )
            .outerjoin(AgentRun, AgentRun.id == InboxEmail.run_id)
            .where(
                InboxEmail.owner_id == owner_id,
                AgentRun.bill_id.is_(None),
                or_(InboxEmail.status.in_(INBOX_ONLY_STATUSES), is_finished_without_bill),
            )
            .order_by(occurred_at.desc())
            .limit(LEDGER_ENTRY_LIMIT)
        )
        if period is not None:
            statement = statement.where(func.to_char(occurred_at, PERIOD_FORMAT) == period)
        if since is not None:
            statement = statement.where(occurred_at >= since)
        if until is not None:
            statement = statement.where(occurred_at < until)
        async with self._sessionmaker() as session:
            rows = (await session.execute(statement)).mappings().all()
        return [_to_inbox_ledger_row(row) for row in rows]

    async def list_runs(
        self,
        owner_id: UUID,
        status: RunStatus | None,
        limit: int,
        run_id: UUID | None = None,
    ) -> list[RunListRow]:
        latest_verdict = (
            select(PaymentDecisionRow.verdict)
            .where(PaymentDecisionRow.run_id == AgentRun.id)
            .order_by(PaymentDecisionRow.created_at.desc())
            .limit(1)
            .scalar_subquery()
        )
        tool_count = (
            select(func.count(AgentRunEvent.id))
            .where(AgentRunEvent.run_id == AgentRun.id, AgentRunEvent.step == TOOL_FINISHED_STEP)
            .scalar_subquery()
        )
        linked_email = (
            select(InboxEmail.id, InboxEmail.subject)
            .where(InboxEmail.run_id == AgentRun.id)
            .limit(1)
            .lateral()
        )
        statement = (
            select(
                AgentRun.id.label("run_id"),
                AgentRun.status,
                AgentRun.created_at,
                AgentRun.updated_at,
                AgentRun.error,
                AgentRun.bill_id,
                BillSourceRow.source_type,
                BillSourceRow.sender,
                linked_email.c.id.label("inbox_email_id"),
                linked_email.c.subject,
                latest_verdict.label("verdict"),
                tool_count.label("tool_count"),
            )
            .outerjoin(BillSourceRow, BillSourceRow.id == AgentRun.bill_source_id)
            .outerjoin(linked_email, true())
            .where(AgentRun.owner_id == owner_id)
            .order_by(AgentRun.created_at.desc())
            .limit(limit)
        )
        if status is not None:
            statement = statement.where(AgentRun.status == status)
        if run_id is not None:
            statement = statement.where(AgentRun.id == run_id)
        async with self._sessionmaker() as session:
            rows = (await session.execute(statement)).mappings().all()
        return [_to_run_list_row(row) for row in rows]


def _decision_statement(owner_id: UUID) -> Select:
    first_source = (
        select(BillSourceRow.source_type, BillSourceRow.inbox_email_id)
        .where(BillSourceRow.bill_id == BillRow.id)
        .order_by(BillSourceRow.created_at)
        .limit(1)
        .lateral()
    )
    return (
        select(
            PaymentDecisionRow.id.label("decision_id"),
            PaymentDecisionRow.created_at.label("decided_at"),
            PaymentDecisionRow.actor,
            PaymentDecisionRow.verdict,
            PaymentDecisionRow.rule_results,
            PaymentDecisionRow.explanation,
            PaymentDecisionRow.note,
            PaymentDecisionRow.run_id,
            BillRow.id.label("bill_id"),
            BillRow.status.label("bill_status"),
            BillRow.duplicate_of_bill_id,
            BillRow.payee_id,
            func.coalesce(PayeeRow.display_name, BillRow.payee_name).label("payee_name"),
            func.coalesce(PayeeRow.kind, BillRow.kind).label("payee_kind"),
            BillRow.category,
            BillRow.amount,
            BillRow.currency,
            BillRow.amount_usd,
            BillRow.fx_usd_per_unit,
            BillRow.fx_rate_date,
            BillRow.fx_source,
            first_source.c.source_type,
            first_source.c.inbox_email_id,
            InboxEmail.subject,
        )
        .join(BillRow, and_(BillRow.id == PaymentDecisionRow.bill_id, BillRow.owner_id == owner_id))
        .outerjoin(PayeeRow, PayeeRow.id == BillRow.payee_id)
        .outerjoin(first_source, true())
        .outerjoin(InboxEmail, InboxEmail.id == first_source.c.inbox_email_id)
        .order_by(PaymentDecisionRow.created_at.desc())
        .limit(LEDGER_ENTRY_LIMIT)
    )


def _to_decision_ledger_row(row: RowMapping) -> DecisionLedgerRow:
    return DecisionLedgerRow(
        decision_id=row["decision_id"],
        decided_at=_as_utc(row["decided_at"]),
        actor=DecisionActor(row["actor"]),
        verdict=Verdict(row["verdict"]),
        rule_results=list(row["rule_results"]),
        explanation=row["explanation"],
        note=row["note"],
        run_id=row["run_id"],
        bill_id=row["bill_id"],
        bill_status=BillStatus(row["bill_status"]),
        duplicate_of_bill_id=row["duplicate_of_bill_id"],
        payee_id=row["payee_id"],
        payee_name=row["payee_name"],
        payee_kind=PayeeKind(row["payee_kind"]) if row["payee_kind"] else None,
        category=PaymentCategory(row["category"]) if row["category"] else None,
        amount=row["amount"],
        currency=row["currency"],
        amount_usd=row["amount_usd"],
        fx_usd_per_unit=row["fx_usd_per_unit"],
        fx_rate_date=row["fx_rate_date"],
        fx_source=FxSource(row["fx_source"]) if row["fx_source"] else None,
        source_type=BillSourceType(row["source_type"]) if row["source_type"] else None,
        inbox_email_id=row["inbox_email_id"],
        subject=row["subject"],
    )


def _to_inbox_ledger_row(row: RowMapping) -> InboxLedgerRow:
    return InboxLedgerRow(
        inbox_email_id=row["inbox_email_id"],
        occurred_at=_as_utc(row["occurred_at"]),
        status=InboxEmailStatus(row["status"]),
        violations=list(row["violations"] or []),
        error=row["error"],
        subject=row["subject"],
        source_type=SOURCE_TYPE_BY_PROVIDER[MailProvider(row["provider"])],
        run_id=row["run_id"],
        run_status=RunStatus(row["run_status"]) if row["run_status"] else None,
        has_extraction_failed=bool(row["has_extraction_failed"]),
    )


def _to_run_list_row(row: RowMapping) -> RunListRow:
    return RunListRow(
        run_id=row["run_id"],
        status=RunStatus(row["status"]),
        created_at=_as_utc(row["created_at"]),
        updated_at=_as_utc(row["updated_at"]),
        error=row["error"],
        bill_id=row["bill_id"],
        source_type=BillSourceType(row["source_type"]) if row["source_type"] else None,
        sender=row["sender"],
        inbox_email_id=row["inbox_email_id"],
        subject=row["subject"],
        verdict=Verdict(row["verdict"]) if row["verdict"] else None,
        tool_count=row["tool_count"],
    )


def _as_utc(stored_at: datetime) -> datetime:
    return stored_at if stored_at.tzinfo else stored_at.replace(tzinfo=UTC)
