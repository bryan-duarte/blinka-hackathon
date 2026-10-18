from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid5

from sqlalchemy import Select, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from contracts.fx import FxSource
from contracts.payment_policy import PaymentCategory
from contracts.payments import (
    CheckerAssessment,
    DecisionActor,
    DecisionRecord,
    LedgerStatus,
    PaymentRecord,
    RuleResult,
    Verdict,
)
from core.logging_config import get_logger
from modules.payments.budget import BudgetCharge
from modules.payments.errors import BudgetExhaustedError, PaymentStateError
from modules.payments.models import (
    BUDGET_COUNTER_CONSTRAINT,
    PAYMENT_BILL_CONSTRAINT,
    BudgetCounterRow,
    PaymentDecisionRow,
    PaymentRow,
)

logger = get_logger(__name__)

PAYMENTS_NAMESPACE = UUID("6f1c9a52-3d7e-4b8a-9a43-2b7f0c5d1e11")
IDEMPOTENCY_KEY_PREFIX = "bill:"
EMPTY_COUNTER_USD = Decimal("0")


@dataclass(frozen=True)
class ReservationRequest:
    owner_id: UUID
    bill_id: UUID
    payee_id: UUID | None
    amount: Decimal
    currency: str
    amount_usd: Decimal
    fx_usd_per_unit: Decimal | None
    fx_rate_date: date | None
    fx_source: FxSource | None
    category: PaymentCategory | None
    period: str
    charges: list[BudgetCharge]


class LedgerRepository:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    async def reserve(self, request: ReservationRequest) -> PaymentRecord:
        payment_insert = (
            insert(PaymentRow)
            .values(
                owner_id=request.owner_id,
                bill_id=request.bill_id,
                idempotency_key=f"{IDEMPOTENCY_KEY_PREFIX}{request.bill_id}",
                payee_id=request.payee_id,
                amount=request.amount,
                currency=request.currency,
                amount_usd=request.amount_usd,
                fx_usd_per_unit=request.fx_usd_per_unit,
                fx_rate_date=request.fx_rate_date,
                fx_source=request.fx_source,
                category=request.category,
                period=request.period,
                scopes=[charge.scope for charge in request.charges],
                status=LedgerStatus.RESERVED,
            )
            .on_conflict_do_nothing(constraint=PAYMENT_BILL_CONSTRAINT)
            .returning(PaymentRow)
        )
        async with self._sessionmaker() as session, session.begin():
            claimed = (await session.execute(payment_insert)).scalar_one_or_none()
            if claimed is None:
                existing = await _payment_for_bill(session, request.bill_id)
                return _to_payment(existing)
            for charge in sorted(request.charges, key=lambda charge: charge.scope):
                await _charge_counter(session, request, charge)
        logger.info("payment_reserved", bill_id=request.bill_id, amount_usd=str(request.amount_usd))
        return _to_payment(claimed)

    # TEMPORAL: dummy rail; replace with the real payout call keyed by idempotency_key.
    async def execute(self, payment_id: UUID) -> PaymentRecord:
        payment = await self._require_payment(payment_id)
        rail_reference = str(uuid5(PAYMENTS_NAMESPACE, payment.idempotency_key))
        statement = (
            update(PaymentRow)
            .where(PaymentRow.id == payment_id, PaymentRow.status == LedgerStatus.RESERVED)
            .values(
                status=LedgerStatus.EXECUTED,
                rail_reference=rail_reference,
                executed_at=func.now(),
                updated_at=func.now(),
            )
            .returning(PaymentRow)
        )
        async with self._sessionmaker() as session:
            executed = (await session.execute(statement)).scalar_one_or_none()
            await session.commit()
        if executed is None:
            return await self._require_payment(payment_id)
        logger.info("payment_executed", payment_id=payment_id, rail_reference=rail_reference)
        return _to_payment(executed)

    async def get_payment(self, payment_id: UUID) -> PaymentRecord | None:
        statement = select(PaymentRow).where(PaymentRow.id == payment_id)
        async with self._sessionmaker() as session:
            payment = (await session.execute(statement)).scalar_one_or_none()
        return _to_payment(payment) if payment else None

    async def payment_for_bill(self, bill_id: UUID) -> PaymentRecord | None:
        async with self._sessionmaker() as session:
            payment = await _payment_for_bill(session, bill_id)
        return _to_payment(payment) if payment else None

    async def reserved_payments(self) -> list[PaymentRecord]:
        statement = select(PaymentRow).where(PaymentRow.status == LedgerStatus.RESERVED)
        async with self._sessionmaker() as session:
            payments = (await session.execute(statement)).scalars().all()
        return [_to_payment(payment) for payment in payments]

    async def append_decision(self, decision: DecisionRecord) -> DecisionRecord:
        decision_row = PaymentDecisionRow(
            bill_id=decision.bill_id,
            run_id=decision.run_id,
            actor=decision.actor,
            actor_user_id=decision.actor_user_id,
            verdict=decision.verdict,
            rule_results=[result.model_dump(mode="json") for result in decision.rule_results],
            checker=decision.checker.model_dump(mode="json") if decision.checker else None,
            explanation=decision.explanation,
            policy_id=decision.policy_id,
            policy_version=decision.policy_version,
            note=decision.note,
        )
        async with self._sessionmaker() as session, session.begin():
            session.add(decision_row)
            await session.flush()
            await session.refresh(decision_row)
        return _to_decision(decision_row)

    async def latest_decision(self, bill_id: UUID) -> DecisionRecord | None:
        decisions = await self._decisions(_newest_decisions_first(bill_id).limit(1))
        return decisions[0] if decisions else None

    async def decision_history(self, bill_id: UUID) -> list[DecisionRecord]:
        return await self._decisions(_newest_decisions_first(bill_id))

    async def latest_decisions(self, bill_ids: list[UUID]) -> dict[UUID, DecisionRecord]:
        if not bill_ids:
            return {}
        statement = (
            select(PaymentDecisionRow)
            .where(PaymentDecisionRow.bill_id.in_(bill_ids))
            .distinct(PaymentDecisionRow.bill_id)
            .order_by(
                PaymentDecisionRow.bill_id,
                PaymentDecisionRow.created_at.desc(),
                PaymentDecisionRow.id.desc(),
            )
        )
        decisions = await self._decisions(statement)
        return {decision.bill_id: decision for decision in decisions}

    async def budget_snapshot(
        self, owner_id: UUID, period: str, scopes: list[str]
    ) -> dict[str, Decimal]:
        if not scopes:
            return {}
        statement = select(BudgetCounterRow.scope, BudgetCounterRow.reserved_usd).where(
            BudgetCounterRow.owner_id == owner_id,
            BudgetCounterRow.period == period,
            BudgetCounterRow.scope.in_(scopes),
        )
        async with self._sessionmaker() as session:
            counters = (await session.execute(statement)).all()
        return {scope: reserved_usd for scope, reserved_usd in counters}

    async def budget_usage(self, owner_id: UUID, period: str) -> dict[str, Decimal]:
        statement = (
            select(BudgetCounterRow.scope, BudgetCounterRow.reserved_usd)
            .where(BudgetCounterRow.owner_id == owner_id, BudgetCounterRow.period == period)
            .order_by(BudgetCounterRow.scope)
        )
        async with self._sessionmaker() as session:
            counters = (await session.execute(statement)).all()
        return {scope: reserved_usd for scope, reserved_usd in counters}

    async def _require_payment(self, payment_id: UUID) -> PaymentRecord:
        payment = await self.get_payment(payment_id)
        if payment is None:
            raise PaymentStateError
        return payment

    async def _decisions(self, statement) -> list[DecisionRecord]:
        async with self._sessionmaker() as session:
            decisions = (await session.execute(statement)).scalars().all()
        return [_to_decision(decision) for decision in decisions]


async def _charge_counter(
    session: AsyncSession, request: ReservationRequest, charge: BudgetCharge
) -> None:
    await session.execute(
        insert(BudgetCounterRow)
        .values(
            owner_id=request.owner_id,
            scope=charge.scope,
            period=request.period,
            reserved_usd=EMPTY_COUNTER_USD,
        )
        .on_conflict_do_nothing(constraint=BUDGET_COUNTER_CONSTRAINT)
    )
    fits_within_limit = BudgetCounterRow.reserved_usd + request.amount_usd <= charge.limit_usd
    charged = (
        await session.execute(
            update(BudgetCounterRow)
            .where(
                BudgetCounterRow.owner_id == request.owner_id,
                BudgetCounterRow.scope == charge.scope,
                BudgetCounterRow.period == request.period,
                fits_within_limit,
            )
            .values(
                reserved_usd=BudgetCounterRow.reserved_usd + request.amount_usd,
                updated_at=func.now(),
            )
            .returning(BudgetCounterRow.reserved_usd)
        )
    ).scalar_one_or_none()
    if charged is None:
        raise BudgetExhaustedError(charge.scope)


def _newest_decisions_first(bill_id: UUID) -> Select[tuple[PaymentDecisionRow]]:
    return (
        select(PaymentDecisionRow)
        .where(PaymentDecisionRow.bill_id == bill_id)
        .order_by(PaymentDecisionRow.created_at.desc(), PaymentDecisionRow.id.desc())
    )


async def _payment_for_bill(session: AsyncSession, bill_id: UUID) -> PaymentRow | None:
    statement = select(PaymentRow).where(PaymentRow.bill_id == bill_id)
    return (await session.execute(statement)).scalar_one_or_none()


def _to_payment(payment: PaymentRow) -> PaymentRecord:
    return PaymentRecord(
        payment_id=payment.id,
        owner_id=payment.owner_id,
        bill_id=payment.bill_id,
        idempotency_key=payment.idempotency_key,
        payee_id=payment.payee_id,
        amount=payment.amount,
        currency=payment.currency,
        amount_usd=payment.amount_usd,
        fx_usd_per_unit=payment.fx_usd_per_unit,
        fx_rate_date=payment.fx_rate_date,
        fx_source=FxSource(payment.fx_source) if payment.fx_source else None,
        category=PaymentCategory(payment.category) if payment.category else None,
        period=payment.period,
        scopes=list(payment.scopes),
        status=LedgerStatus(payment.status),
        rail_reference=payment.rail_reference,
        executed_at=payment.executed_at,
        created_at=payment.created_at,
    )


def _to_decision(decision: PaymentDecisionRow) -> DecisionRecord:
    return DecisionRecord(
        decision_id=decision.id,
        bill_id=decision.bill_id,
        run_id=decision.run_id,
        actor=DecisionActor(decision.actor),
        actor_user_id=decision.actor_user_id,
        verdict=Verdict(decision.verdict),
        rule_results=[RuleResult.model_validate(result) for result in decision.rule_results],
        checker=CheckerAssessment.model_validate(decision.checker) if decision.checker else None,
        explanation=decision.explanation,
        policy_id=decision.policy_id,
        policy_version=decision.policy_version,
        note=decision.note,
        created_at=decision.created_at,
    )
