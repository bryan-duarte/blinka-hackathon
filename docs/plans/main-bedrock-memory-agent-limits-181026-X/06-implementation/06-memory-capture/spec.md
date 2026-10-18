# Memory Capture ("Remember this" on approve/reject)

## Overview

Approve and reject accept `remember: bool`. When it is true, the decision settles first, exactly as today. After that, `PaymentsService` hands a `DecisionMemoryInput` to `memory.remember_decision_later(...)`, which runs in the background. The UI adds a checkbox under the note.

## Files to Modify/Create

- `backend/contracts/payments.py:197`: `ReviewActionRequest.remember: bool = False`.
- `backend/modules/payments/service.py`:
  - `PaymentsService.__init__` takes a `memory: "MemoryClient"` keyword.
  - `approve` (`:206-231`) and `reject` (`:233-254`) call `_remember(...)`.
  - New private method `_remember(owner, bill, request, human_action, resulting_verdict, escalation_source)`.
- `backend/container.py:154-161`: pass `memory=memory` to `PaymentsService(...)`.
- `frontend/src/lib/api.ts:217-220`:
  - `approveBill(billId, note, remember)` posts `{ note, remember }`.
  - `rejectBill(billId, note, remember)` posts `{ note, remember }`.
- `frontend/src/components/bills/ReviewActions.tsx`:
  - New `remember` state (default `false`).
  - Checkbox between the textarea block (ends `:67`) and the error/buttons (`:68`).
  - Pass `remember` to both API calls, and reset it to `false` after resolve.

## Implementation Guidelines

```python
# orientative — payments/service.py
async def approve(self, owner, bill_id, request) -> BillDecisionView:
    bill = await self._claim_review(owner, bill_id, BillStatus.APPROVING)
    escalation = await self._dependencies.ledger.latest_decision(bill_id)   # the agent's REVIEW decision, read before settling
    policy = None
    try:
        ...  # unchanged
    except Exception:
        logger.exception("bill_review_approval_failed", bill_id=bill_id)
        await fail_closed(self._dependencies, None, bill, policy)
    else:
        logger.info("bill_review_approved", bill_id=bill_id, verdict=decision.verdict)
        if request.remember:
            self._remember(owner, bill, request.note, "approved", decision.verdict, escalation)
    return await self._require_bill_decision(owner, bill_id)

async def reject(self, owner, bill_id, request) -> BillDecisionView:
    bill = await self._claim_review(owner, bill_id, BillStatus.REJECTED)   # keep the returned BillRecord
    latest = await self._dependencies.ledger.latest_decision(bill_id)
    ...  # unchanged append_decision
    if request.remember:
        self._remember(owner, bill, request.note, "rejected", Verdict.HOLD, latest)
    return await self._require_bill_decision(owner, bill_id)

def _remember(self, owner, bill: BillRecord, note: str, human_action, resulting_verdict: Verdict,
              escalation: DecisionRecord | None) -> None:
    escalation_reasons = [
        result.reason for result in (escalation.rule_results if escalation else [])
        if result.effect is not RuleEffect.PASS
    ]
    self._memory.remember_decision_later(
        DecisionMemoryInput(
            owner_id=owner.user_id, actor_user_id=owner.user_id, bill_id=bill.bill_id,
            payee_id=bill.payee_id, payee_name=bill.payee_name,
            amount=bill.amount, currency=bill.currency, amount_usd=bill.amount_usd, category=bill.category,
            escalation_reasons=escalation_reasons, human_action=human_action,
            resulting_verdict=resulting_verdict, note=note, decided_at=datetime.now(UTC),
        )
    )
```
- `_remember` is synchronous because it only spawns. It must never raise into the HTTP path. Wrap it in a `try/except Exception: logger.exception("memory_capture_failed")` so a contract validation issue can't break approve/reject.
- If the checker raised concerns (`escalation.checker`), append their rationales to `escalation_reasons` as well. Answers that drove review carry the most useful context for the lesson.
- Confirm the exact `BillRecord` field names (`amount`, `currency`, `amount_usd`, `category`, `payee_id`, `payee_name`) in `contracts/bills.py:~70-80` and adjust. `DecisionMemoryInput` is `StrictModel`, so pass correctly typed values (Decimal, not str).
- Approve failure path (`except` → `fail_closed`): don't remember.

```tsx
// orientative — ReviewActions.tsx
const [remember, setRemember] = useState(false);
...
<label className="flex items-center gap-2 text-sm">
  <input
    type="checkbox"
    checked={remember}
    onChange={(event) => setRemember(event.target.checked)}
    disabled={pendingAction !== null}
  />
  Remember this for future invoices from this payee
</label>
<p className="text-xs ...">The agent will use it as context next time. It never overrides your payment rules.</p>
```
- Style per `frontend/DESIGN.md`: re-read it fully first, use its tokens and checkbox treatment, no em-dashes in copy.

## Dependencies

- Module 05 (`MemoryClient`, `DecisionMemoryInput`).

## Integration Notes

- `ReviewActionRequest` uses `ApiModel` with `extra="forbid"`. Deploy the backend before the frontend, or older backends return 422 on `remember`.
- The response shape (`BillDecisionView`) is unchanged. The UI doesn't wait for extraction; memories appear in `/settings/memories` after a few seconds.
