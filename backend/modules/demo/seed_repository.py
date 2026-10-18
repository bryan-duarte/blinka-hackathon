from collections import defaultdict
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4, uuid5

from sqlalchemy.dialects.postgresql import Insert, insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from contracts.payment_policy import PayeeView, PaymentPolicy
from contracts.payments import DecisionActor, LedgerStatus
from modules.bills.hashing import bill_fingerprint, normalize_invoice_number
from modules.bills.models import BillRow
from modules.demo.seed_data import HistoricalBill, HistoricalDecision
from modules.payment_policy import normalize_name
from modules.payments.budget import budget_charges
from modules.payments.ledger_repository import IDEMPOTENCY_KEY_PREFIX, PAYMENTS_NAMESPACE
from modules.payments.models import (
    BUDGET_COUNTER_CONSTRAINT,
    BudgetCounterRow,
    PaymentDecisionRow,
    PaymentRow,
)

BudgetKey = tuple[str, str]


class DemoSeedRepository:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    async def insert_history(
        self,
        owner_id: UUID,
        policy: PaymentPolicy,
        payees_by_name: dict[str, PayeeView],
        bills: list[HistoricalBill],
    ) -> int:
        latest_allowed = datetime.now(UTC).replace(tzinfo=None)
        bills = [_not_in_future(bill, latest_allowed) for bill in bills]
        bill_ids = {bill.key: uuid4() for bill in bills}
        bill_rows = [_bill_row(owner_id, bill, bill_ids, payees_by_name) for bill in bills]
        decision_rows = [
            _decision_row(owner_id, policy, bill_ids[bill.key], decision)
            for bill in bills
            for decision in bill.decisions
        ]
        paid_bills = [bill for bill in bills if bill.is_paid]
        payment_rows = [
            _payment_row(owner_id, policy, bill_ids[bill.key], bill, payees_by_name)
            for bill in paid_bills
        ]
        counter_rows = _counter_rows(owner_id, payment_rows)
        async with self._sessionmaker() as session, session.begin():
            await session.execute(insert(BillRow), bill_rows)
            await session.execute(insert(PaymentDecisionRow), decision_rows)
            if payment_rows:
                await session.execute(insert(PaymentRow), payment_rows)
            if counter_rows:
                await session.execute(_upsert_counters(counter_rows))
        return len(bill_rows)


def _bill_row(
    owner_id: UUID,
    bill: HistoricalBill,
    bill_ids: dict[str, UUID],
    payees_by_name: dict[str, PayeeView],
) -> dict:
    payee = payees_by_name.get(bill.payee_name) if bill.is_registered_payee else None
    invoice_number = normalize_invoice_number(bill.invoice_number)
    payee_key = str(payee.payee_id) if payee else normalize_name(bill.payee_name)
    created_at = bill.decisions[0].decided_at
    return {
        "id": bill_ids[bill.key],
        "owner_id": owner_id,
        "kind": bill.kind,
        "payee_id": payee.payee_id if payee else None,
        "payee_name": bill.payee_name,
        "invoice_number": invoice_number,
        "amount": bill.amount,
        "currency": bill.currency,
        "amount_usd": bill.amount_usd,
        "fx_usd_per_unit": bill.quote.usd_per_unit,
        "fx_rate_date": bill.quote.rate_date,
        "fx_source": bill.quote.source,
        "category": bill.category,
        "due_date": bill.due_on,
        "candidate": bill.candidate,
        "document_sha256": None,
        "fingerprint": bill_fingerprint(
            owner_id, payee_key, invoice_number, bill.due_on, bill.amount, bill.currency
        ),
        "duplicate_of_bill_id": bill_ids[bill.duplicate_of_key] if bill.duplicate_of_key else None,
        "status": bill.final_status,
        "version": len(bill.decisions),
        "created_at": created_at,
        "updated_at": bill.decisions[-1].decided_at,
    }


def _decision_row(
    owner_id: UUID, policy: PaymentPolicy, bill_id: UUID, decision: HistoricalDecision
) -> dict:
    is_human = decision.actor is DecisionActor.HUMAN
    return {
        "id": uuid4(),
        "bill_id": bill_id,
        "run_id": None,
        "actor": decision.actor,
        "actor_user_id": owner_id if is_human else None,
        "verdict": decision.verdict,
        "rule_results": [
            rule_result.model_dump(mode="json") for rule_result in decision.rule_results
        ],
        "checker": None,
        "explanation": decision.explanation,
        "policy_id": policy.policy_id,
        "policy_version": policy.version,
        "note": decision.note,
        "created_at": decision.decided_at,
    }


def _payment_row(
    owner_id: UUID,
    policy: PaymentPolicy,
    bill_id: UUID,
    bill: HistoricalBill,
    payees_by_name: dict[str, PayeeView],
) -> dict:
    payee = payees_by_name.get(bill.payee_name)
    idempotency_key = f"{IDEMPOTENCY_KEY_PREFIX}{bill_id}"
    charges = budget_charges(policy, payee, bill.category)
    return {
        "id": uuid4(),
        "owner_id": owner_id,
        "bill_id": bill_id,
        "idempotency_key": idempotency_key,
        "payee_id": payee.payee_id if payee else None,
        "amount": bill.amount,
        "currency": bill.currency,
        "amount_usd": bill.amount_usd,
        "fx_usd_per_unit": bill.quote.usd_per_unit,
        "fx_rate_date": bill.quote.rate_date,
        "fx_source": bill.quote.source,
        "category": bill.category,
        "period": f"{bill.paid_at:%Y-%m}",
        "scopes": [charge.scope for charge in charges],
        "status": LedgerStatus.EXECUTED,
        "rail_reference": str(uuid5(PAYMENTS_NAMESPACE, idempotency_key)),
        "executed_at": bill.paid_at,
        "created_at": bill.paid_at,
        "updated_at": bill.paid_at,
    }


def _counter_rows(owner_id: UUID, payment_rows: list[dict]) -> list[dict]:
    reserved_by_scope: dict[BudgetKey, Decimal] = defaultdict(Decimal)
    for payment in payment_rows:
        for scope in payment["scopes"]:
            reserved_by_scope[(scope, payment["period"])] += payment["amount_usd"]
    return [
        {"owner_id": owner_id, "scope": scope, "period": period, "reserved_usd": reserved_usd}
        for (scope, period), reserved_usd in reserved_by_scope.items()
    ]


def _upsert_counters(counter_rows: list[dict]) -> Insert:
    statement = insert(BudgetCounterRow).values(counter_rows)
    return statement.on_conflict_do_update(
        constraint=BUDGET_COUNTER_CONSTRAINT,
        set_={"reserved_usd": BudgetCounterRow.reserved_usd + statement.excluded.reserved_usd},
    )


def _not_in_future(bill: HistoricalBill, latest_allowed: datetime) -> HistoricalBill:
    decisions = tuple(
        replace(decision, decided_at=min(decision.decided_at, latest_allowed))
        for decision in bill.decisions
    )
    return replace(bill, decisions=decisions)
