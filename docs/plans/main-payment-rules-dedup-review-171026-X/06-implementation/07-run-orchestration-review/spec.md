# Run Orchestration & Human Review Implementation

## Overview

Rewrite `modules/payments/runner.py` as a fixed pipeline with no agent loop. Make `start_run` idempotent per bill source. Add the review actions (approve and reject), the bill queries and the startup recovery sweep to `PaymentsService`. Delete the deep agent and `execute_payment`.

## Files to Modify/Create

- `modules/payments/runner.py`: rewrite. `PaymentRunDependencies` drops `payments_checkpointer` and adds `ledger: LedgerRepository`, `bills: "BillsClient"` and `policy: "PaymentPolicyClient"`. Final fields: `repository`, `ledger`, `bills`, `policy`, `invoice_ingestor`, `llm_gateway` (checker), `prompts`, `sessions`.
- `modules/payments/settlement.py` (new): `settle(...)`, the shared reserve, execute, record and transition sequence, used by both the runner and the approval path.
- `modules/payments/service.py`:
  - `start_run` becomes idempotent.
  - New methods: `list_bills`, `get_bill`, `approve`, `reject`, `budget_usage`, `recover_unfinished_payments`.
  - `get_run` returns `decision`.
- `modules/payments/repository.py`:
  - `insert_run(...) -> tuple[UUID, bool]` uses ON CONFLICT with the partial index.
  - New: `find_active_run(bill_source_id)` and `latest_run_for_source(bill_source_id) -> PaymentRunRecord`, which orders by `created_at DESC`.
- `modules/payments/agent.py`: delete (removes `execute_payment`, `convert_to_clp`, `DUMMY_CLP_RATES` and the deep agent).
- `modules/payments/__init__.py`, `clients/payments.py`: export and expose the new methods.
- `container.py`: build `PaymentRunDependencies` with the new fields (see 09).

## Implementation Guidelines

### Idempotent `start_run`

```python
async def start_run(self, trigger: PaymentRunTrigger, owner: CurrentUser) -> PaymentRunAccepted:
    source = await self._bills.get_source(owner, trigger.bill_source_id)
    if source.bill_id is not None:
        previous_run = await self._repository.latest_run_for_source(source.source_id)
        return PaymentRunAccepted(run_id=previous_run.run_id, status=previous_run.status, duplicate=True)
    run_id, created = await self._repository.insert_run(
        agent=PAYMENTS_AGENT_NAME, owner_id=owner.user_id, file_id=source.file_id,
        session_id=trigger.session_id, bill_source_id=source.source_id)
    if created:
        self._registry.spawn(run_id, run_execution(run_id, owner, source.source_id, trigger.session_id, self._dependencies))
        logger.info("payment_run_started", run_id=run_id, bill_source_id=source.source_id)
    return PaymentRunAccepted(run_id=run_id, status=RunStatus.PENDING, duplicate=not created)
```

The repository's `insert_run` uses:

```python
insert(AgentRun).values(...).on_conflict_do_nothing(
    index_elements=[AgentRun.bill_source_id],
    index_where=AgentRun.status.in_(ACTIVE_STATUSES)).returning(AgentRun.id)
```

When nothing is returned, it falls back to `find_active_run`. It returns `(id, False)` when a run is already active.

### Run pipeline

The step names are UPPER constants, and each step writes an `agent_run_events` row with the same name.

```python
async def _decide_source(run_id, owner, source_id, deps) -> None:
    source = await deps.bills.get_source(owner, source_id)
    document = BillDocument(body_text=source.body_text, file_id=source.file_id, sender=source.sender)
    classification = await deps.invoice_ingestor.classify(owner, document)
    await deps.repository.insert_event(run_id, CLASSIFIED_STEP, classification.model_dump(mode="json"))
    if not classification.is_bill or classification.kind is None:
        await deps.repository.insert_event(run_id, NOT_A_BILL_STEP, {"reason": classification.reason})
        return
    candidate = await deps.invoice_ingestor.extract_candidate(owner, document, classification.kind)
    await deps.repository.insert_event(run_id, EXTRACTED_STEP, candidate.model_dump(mode="json"))

    policy = await deps.policy.get_policy(owner)
    match = await deps.policy.match_payee(owner.user_id, candidate, source.sender)
    amount_usd = to_usd(candidate.amount, candidate.currency) if candidate.amount and candidate.currency else None
    claim = await deps.bills.claim_bill(owner, source, bill_fields(owner, source, candidate, match, amount_usd))
    await deps.repository.set_run_bill(run_id, claim.bill.bill_id)

    if claim.duplicate_of is not None:
        await record_duplicate(deps, run_id, owner, claim, policy)        # HOLD "DUP", explanation names the original
        return

    try:
        context = await build_context(deps, owner, source, candidate, classification, match, policy, amount_usd, claim.bill)
        evaluation = decide(context)
        if evaluation.verdict is Verdict.PAY:
            assessment = await run_checker(deps.llm_gateway, deps.prompts, context)
            evaluation = apply_checker(evaluation, assessment, policy)
        await settle(deps, run_id, owner, claim.bill, context, evaluation, actor=DecisionActor.AGENT)
    except Exception:
        logger.exception("bill_decision_failed", run_id=run_id, bill_id=claim.bill.bill_id)
        await record_technical_review(deps, run_id, owner, claim.bill, policy)   # REVIEW "error_tecnico"
```

- The catch-all only wraps the steps after `claim_bill`. Before a bill exists, failures keep today's behavior: the run is FAILED, and the inbox shows ERROR or NO_INVOICE.
- `record_technical_review` must itself be safe: it appends the decision, then attempts `transition(DECIDING → REVIEW)`.
- `PolicyMissingError` is raised before the claim, so the run FAILS with the error "payment policy not configured". That is a clear setup error for the demo.

### `settle`: the one place money moves

```python
async def settle(deps, run_id, owner, bill, context, evaluation, actor, actor_user_id=None, note=None,
                 from_status=BillStatus.DECIDING) -> DecisionRecord:
    verdict, results = evaluation.verdict, evaluation.results
    if verdict is Verdict.PAY:
        try:
            payment = await deps.ledger.reserve(reservation_request(owner, bill, context))
            await deps.ledger.execute(payment.payment_id)
        except BudgetExhaustedError as exhausted:
            verdict = Verdict.HOLD
            results = [*results, budget_exhausted_result(str(exhausted))]   # R14, reason "presupuesto agotado al reservar: <scope>"
            logger.info("budget_exhausted", bill_id=bill.bill_id, scope=str(exhausted))
    decision = await deps.ledger.append_decision(DecisionRecord(
        bill_id=bill.bill_id, run_id=run_id, actor=actor, actor_user_id=actor_user_id, verdict=verdict,
        rule_results=results, checker=context_checker(results), explanation=explain(RuleEvaluation(verdict, results), context),
        policy_id=context.policy.policy_id, policy_version=context.policy.version, note=note))
    await deps.bills.transition(owner, bill.bill_id, from_status, VERDICT_STATUS[verdict])
    return decision
```

`VERDICT_STATUS = {PAY: PAID, HOLD: HELD, REVIEW: REVIEW}`.

**Ordering invariant.** The ledger is written first, then the decision, then the bill status. A crash at any point leaves a state the sweep can complete. Because of the bill's compare-and-set transition, a second settle for the same bill can't flip a final state.

### Human review

```python
async def approve(self, owner, bill_id, request: ReviewActionRequest) -> BillDecisionView:
    bill = await self._bills.transition(owner, bill_id, BillStatus.REVIEW, BillStatus.APPROVING)   # 409 if not review
    context = await self._rebuild_context(owner, bill)        # fresh policy, match, budget snapshot
    evaluation = decide(replace(context, waived_effects=frozenset({RuleEffect.REVIEW})))
    decision = await settle(self._dependencies, None, owner, bill, context, evaluation,
                            actor=DecisionActor.HUMAN, actor_user_id=owner.user_id, note=request.note,
                            from_status=BillStatus.APPROVING)
    logger.info("bill_review_approved", bill_id=bill_id, verdict=decision.verdict)
    return await self._view(owner, bill_id)

async def reject(self, owner, bill_id, request) -> BillDecisionView:
    bill = await self._bills.transition(owner, bill_id, BillStatus.REVIEW, BillStatus.REJECTED)
    await self._ledger.append_decision(DecisionRecord(bill_id=bill_id, actor=HUMAN, verdict=Verdict.HOLD,
        rule_results=latest.rule_results, explanation=f"Rechazada por una persona: {request.note}", ...))
    ...
```

- `_rebuild_context` rebuilds `DecisionContext` from `bill.candidate` (validated with `TypeAdapter(PaymentCandidate)`), the bill's first source, and fresh policy, match, blacklist, recent bills and budget. Approval re-runs R03 (blacklist) and R05 (identity) against the current registry. If someone blacklisted the account in the meantime, approval holds the bill.
- Approving can still end in HOLD, from a HOLD rule or from the budget at reservation time. The UI shows the resulting decision.
- **Concurrent approve and reject:** the first to win the `REVIEW → APPROVING|REJECTED` compare-and-set proceeds, and the other gets `BillStateConflictError`, mapped to 409.
- **Double-click approve:** the second request hits the same 409. Even if it didn't, `uq_payments_bill_id` would make the reservation a no-op.

### Queries

- `list_bills(owner, status)` combines `bills.list_bills` with `ledger.latest_decisions`, mapped to `BillDecisionView`.
- `get_bill(owner, bill_id)` returns `BillDetail`: the latest decision, the history, the sources and the payment.
- `budget_usage(owner, period)` returns the limits from the policy and payees plus `reserved_usd` from the counters.
- `get_run` builds `decision` from `ledger.latest_decision(run.bill_id)` when `bill_id` is set. `is_bill=False` when the run has a `not_a_bill` event.

### Startup recovery (`recover_unfinished_payments`)

The order in `api/app.py` lifespan is `payments.fail_unfinished(...)`, then `payments.recover_unfinished_payments()`, then `inbox.fail_unfinished(...)`.

1. For each payment in `reserved_payments()`, call `execute`.
2. For each bill in `bills.stuck_bills((DECIDING, APPROVING))`:
   - If the payment is executed: append PAY "pago completado tras reinicio" and transition to PAID.
   - Otherwise: append REVIEW `error_tecnico` "interrumpido por reinicio" and transition to REVIEW.
3. Log `unfinished_bills_recovered` with counts.

## Dependencies

- Modules 03 (bills), 04 (extraction), 05 (rules, checker, explain) and 06 (ledger, budget).
- `clients/payment_policy.py`.

## Integration Notes

- `_record_execution` (sessions) stays for chat-triggered runs. Its output summary becomes `decision.explanation[:500]`, and its input becomes `f"{candidate.kind} {candidate.payee_name} {candidate.amount} {candidate.currency}"`.
- `PaymentRunStatus.decision` is what both the inbox and the orchestrator read.
