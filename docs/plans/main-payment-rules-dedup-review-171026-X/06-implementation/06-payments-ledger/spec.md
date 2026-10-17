# Payments Ledger Implementation

## Overview

This is the money layer in `modules/payments`. It keeps the append-only decision log and the `payments` ledger, which allows one row per bill. It also owns the budget counters per scope and month. Reserving budget is atomic and race-safe. Executing the dummy payment is exactly-once. A recovery sweep runs at startup.

## Files to Modify/Create

- `modules/payments/models.py`
  - Add `PaymentDecisionRow`, `PaymentRow` and `BudgetCounterRow`. Columns and named constraints are in `03-design.md`.
  - Add `bill_source_id`, `bill_id` and `Index("uq_agent_runs_active_source", ...)` to `AgentRun`.
- `modules/payments/ledger_repository.py` (new): `LedgerRepository(sessionmaker)`.
- `modules/payments/repository.py`:
  - `insert_run` takes `bill_source_id` and becomes idempotent (see 07).
  - Add `set_run_bill(run_id, bill_id)`.
- `modules/payments/errors.py`: add `BudgetExhaustedError` (internal, never reaches HTTP), `PaymentStateError`, `BillNotReviewableError` (409 "bill is not awaiting review").

## Implementation Guidelines

### Scopes and limits (computed by the caller, not read here)

```python
@dataclass(frozen=True)
class BudgetCharge:
    scope: str          # "global" | "category:cloud" | "payee:<uuid>"
    limit_usd: Decimal

def budget_charges(policy: PaymentPolicy, payee: PayeeRecord, category: PaymentCategory | None) -> list[BudgetCharge]:
    charges = [BudgetCharge("global", policy.monthly_budget_usd)]
    if category and category in policy.category_monthly_budgets_usd:
        charges.append(BudgetCharge(f"category:{category}", policy.category_monthly_budgets_usd[category]))
    if payee.monthly_budget_usd is not None:
        charges.append(BudgetCharge(f"payee:{payee.payee_id}", payee.monthly_budget_usd))
    return sorted(charges, key=lambda charge: charge.scope)
```

This lives in `modules/payments/budget.py` (new). The runner and the approval path both call it with the policy and payee they just loaded. Sorting by scope fixes the lock order so concurrent reservations can't deadlock.

### reserve: one transaction, exactly one payment per bill, never over budget

```python
async def reserve(self, request: ReservationRequest) -> PaymentRecord:
    async with self._sessionmaker() as session, session.begin():
        claimed = (await session.execute(
            insert(PaymentRow).values(
                owner_id=request.owner_id, bill_id=request.bill_id,
                idempotency_key=f"bill:{request.bill_id}", payee_id=request.payee_id,
                amount=request.amount, currency=request.currency, amount_usd=request.amount_usd,
                category=request.category, period=request.period,
                scopes=[charge.scope for charge in request.charges], status=LedgerStatus.RESERVED)
            .on_conflict_do_nothing(constraint="uq_payments_bill_id")
            .returning(PaymentRow))).scalar_one_or_none()
        if claimed is None:
            existing = await self._payment_for_bill(session, request.bill_id)
            return _to_payment_record(existing)          # idempotent replay: no second charge
        for charge in request.charges:
            await session.execute(insert(BudgetCounterRow)
                .values(owner_id=request.owner_id, scope=charge.scope, period=request.period, reserved_usd=0)
                .on_conflict_do_nothing(constraint="pk_budget_counters"))
            charged = (await session.execute(update(BudgetCounterRow)
                .where(BudgetCounterRow.owner_id == request.owner_id,
                       BudgetCounterRow.scope == charge.scope,
                       BudgetCounterRow.period == request.period,
                       BudgetCounterRow.reserved_usd + request.amount_usd <= charge.limit_usd)
                .values(reserved_usd=BudgetCounterRow.reserved_usd + request.amount_usd, updated_at=func.now())
                .returning(BudgetCounterRow.reserved_usd))).scalar_one_or_none()
            if charged is None:
                raise BudgetExhaustedError(charge.scope)   # rolls back the payment row and earlier counters
    return _to_payment_record(claimed)
```

Why this is race-safe under READ COMMITTED:
- The conditional `UPDATE` takes the counter row lock. A concurrent reserver blocks on that lock. After the first transaction commits, Postgres re-evaluates the `WHERE` against the new `reserved_usd`. The second reserver either fits or gets 0 rows. It never pushes the counter past the limit.
- `uq_payments_bill_id` makes a second reservation for the same bill a no-op that returns the first one, whether it comes from a retry, a double approve or a parallel run.
- `BudgetExhaustedError` propagates out of `session.begin()`, so everything in the transaction rolls back. The bill ends with no payment row, and the runner records HOLD (R14 "presupuesto agotado").

`ReservationRequest` is a frozen dataclass in `ledger_repository.py` with `owner_id`, `bill_id`, `payee_id`, `amount`, `currency`, `amount_usd`, `category`, `period` and `charges`.

### execute: exactly-once dummy pay

```python
PAYMENTS_NAMESPACE = UUID("6f1c9a52-3d7e-4b8a-9a43-2b7f0c5d1e11")

async def execute(self, payment_id: UUID) -> PaymentRecord | None:
    payment = await self.get_payment(payment_id)
    rail_reference = str(uuid5(PAYMENTS_NAMESPACE, payment.idempotency_key))
    statement = (update(PaymentRow)
        .where(PaymentRow.id == payment_id, PaymentRow.status == LedgerStatus.RESERVED)
        .values(status=LedgerStatus.EXECUTED, rail_reference=rail_reference,
                executed_at=func.now(), updated_at=func.now())
        .returning(PaymentRow))
    ...
```

- Return `None` when the row was already executed. The caller then reads the row and treats it as success, so execution is idempotent.
- The "dummy rail" is this compare-and-set plus a `payment_executed` log line. Add `# TEMPORAL: dummy rail; replace with the real payout call keyed by idempotency_key.` above `execute`. When a real rail exists, it must receive `idempotency_key` and be called between claiming and confirming.

### No release path

Do not implement `release`. No flow cancels a reserved payment: the recovery sweep re-executes it instead. Keep `LedgerStatus.RELEASED` out of the enum until a cancel flow exists. Revisit this when a real rail can reject a payout.

### Decisions (append-only)

- `append_decision(record: DecisionRecord) -> DecisionRecord` runs an INSERT only. There is no update path.
- `latest_decision(bill_id) -> DecisionRecord | None` uses `ORDER BY created_at DESC, id DESC LIMIT 1`.
- `decision_history(bill_id) -> list[DecisionRecord]`
- `latest_decisions(owner_id, bill_ids) -> dict[UUID, DecisionRecord]` uses `DISTINCT ON (bill_id)` to back `GET /bills`.

### Budget reads

- `budget_snapshot(owner_id, period, scopes) -> dict[str, Decimal]` feeds rule R14.
- `budget_usage(owner_id, period) -> list[(scope, reserved_usd)]` feeds `GET /budgets`, where the service joins the limits from the policy and the payees.

### Recovery

`reserved_payments() -> list[PaymentRecord]` returns the payments the startup sweep re-executes.

## Dependencies

`contracts/payments.py`, `contracts/payment_policy.py` (`PaymentPolicy`, `PayeeRecord`, `PaymentCategory`), and `sqlalchemy.dialects.postgresql.insert`.

## Integration Notes

- The runner and the approval path call, in this order: `budget_charges` → `reserve` → `execute` → `append_decision` → `bills.transition`.
- If the process dies between `reserve` and `append_decision`, the startup sweep finds the bill in `deciding`/`approving` and a payment that is reserved or executed:
  - **Payment executed:** append a PAY decision with the reason "pago completado tras reinicio" and transition the bill to `paid`.
  - **Payment reserved:** call `execute`, then do the same.
  - **No payment:** append REVIEW `error_tecnico`.
- See 07 for the sweep itself.
