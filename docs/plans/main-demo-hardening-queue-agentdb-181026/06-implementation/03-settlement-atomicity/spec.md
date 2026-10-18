# Settlement Atomicity Implementation

## Overview

Fix the one critical ordering bug: `settle()` reserves and executes the payment (tx1, tx2), appends the decision (tx3) and only then compare-and-sets the bill status (tx4). After this change the bill CAS, the payment reserve and execute, and the decision insert commit in **one** product-DB transaction. If the CAS misses, nothing is written and no money moves.

## Files to Modify/Create

- `backend/modules/payments/ledger_repository.py`
  - Add `commit_settlement(...)`, a single transaction.
  - Extract `_insert_reservation(session, request) -> PaymentRow` from `reserve()` (lines 59-89) so `reserve()` and `commit_settlement` share it.
  - Extract `_execute_in_session(session, payment_row) -> PaymentRow` from `execute()` (lines 91-112).
  - Extract `_decision_row(decision) -> PaymentDecisionRow` from `append_decision()` (lines 131-149).
  - Keep `reserve`, `execute` and `append_decision` public for the recovery paths (`fail_closed`, `record_recovered_payment`, `record_technical_review`, `record_duplicate`, `reject`).
- `backend/modules/payments/settlement.py`
  - `settle()` (lines 55-92): build the reservation and decision, call `commit_settlement`, and on `BudgetExhaustedError` rebuild as HOLD and commit again.
  - `_pay()` (lines 189-229) becomes `_reservation_for(bill, context) -> ReservationRequest | RuleResult` (a pure builder that returns the UNPAYABLE blocker when the bill can't be paid).
- `backend/modules/payments/ledger_repository.py` imports `BillRow` from `modules.bills.models` and `BillStateConflictError` from `modules.bills.errors`. Add a one-line comment saying this is the only cross-module write and why.

## Implementation Guidelines

```python
# ledger_repository.py (orientative)
async def commit_settlement(
    self,
    owner_id: UUID,
    bill_id: UUID,
    from_status: BillStatus,
    target_status: BillStatus,
    reservation: ReservationRequest | None,
    decision: DecisionRecord,
) -> DecisionRecord:
    # Bill CAS shares the money transaction so funds never move for a bill whose state changed.
    bill_claim = (
        update(BillRow)
        .where(BillRow.id == bill_id, BillRow.owner_id == owner_id, BillRow.status == from_status)
        .values(status=target_status, version=BillRow.version + 1, updated_at=func.now())
        .returning(BillRow.id)
    )
    async with self._sessionmaker() as session, session.begin():
        if (await session.execute(bill_claim)).scalar_one_or_none() is None:
            raise BillStateConflictError
        if reservation is not None:
            payment = await _insert_reservation(session, reservation)   # raises BudgetExhaustedError → rollback
            await _execute_in_session(session, payment)
        decision_row = _decision_row(decision)
        session.add(decision_row)
        await session.flush()
        await session.refresh(decision_row)
    logger.info("bill_settled", bill_id=bill_id, target_status=target_status, is_paid=reservation is not None)
    return _to_decision(decision_row)
```

```python
# settlement.py settle() (orientative)
verdict, results = evaluation.verdict, list(evaluation.results)
reservation = None
if verdict is Verdict.PAY:
    planned = _reservation_for(bill, context)
    if isinstance(planned, RuleResult):
        verdict, results = Verdict.HOLD, [*results, planned]
    else:
        reservation = planned
try:
    return await _commit(dependencies, run_id, bill, context, verdict, results, reservation, actor, from_status, ...)
except BudgetExhaustedError as exhausted:
    blocker = _budget_blocker(exhausted, context.match.payee)        # same R14 text as today
    return await _commit(dependencies, ..., Verdict.HOLD, [*results, blocker], None, ...)
```

- `_commit` builds the `DecisionRecord` with `explain(verdict, results, context)` and calls `ledger.commit_settlement(..., target_status=VERDICT_STATUS[verdict])`.
- Keep the existing `logger.info("bill_decided", ...)` and the `budget_exhausted` log.
- **Idempotent replay.** `_insert_reservation` keeps `ON CONFLICT DO NOTHING` on `uq_payments_bill_id`. If a payment for this bill already exists (legacy recovery), return the existing row, and only execute it when it is still `RESERVED`. In practice the bill CAS already prevents a second settle for the same bill from reaching this point.
- `BillStateConflictError` propagates unchanged. The run's `_finalize` / `fail_closed` already handle it, and the HTTP mapping is 409 (`api/app.py:78`).
- `PaymentRunDependencies.ledger` must expose `commit_settlement`. Check whether it is the repository itself or a client wrapper (`modules/payments/dependencies.py`), and add a passthrough if it is a wrapper.

## Dependencies

- None from other modules in this plan. Implement it before module 04 so the queued runs use the safe path.

## Integration Notes

- **Callers:** `settle()` is called by `agent_tools._settle_decision` (`from_status=DECIDING`) and `PaymentsService.approve` (`from_status=APPROVING`). Their signatures do not change.
- **Recovery:** `recover_unfinished_payments` (`service.py:263-284`) stays. It now only ever finds legacy `RESERVED` rows.
- **Out of scope (user choice):** the `reject()` ordering and decision uniqueness.
