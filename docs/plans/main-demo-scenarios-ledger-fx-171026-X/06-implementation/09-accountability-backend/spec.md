# Accountability Read Model & Run Trace Implementation

## Overview

This is a read-only backend that serves four things: the agent's ledger (every outcome, its reasons, and both original and USD amounts), summary aggregates for the charts, a CSV export, and the list of all runs. It also adds the full LLM trace endpoint, which reads the LangGraph checkpoint.

## Files to Modify/Create

- `backend/contracts/accountability.py` (new): `LedgerOutcome`, `LEDGER_TAB_OUTCOMES`, `LedgerReason`, `LedgerEntryView`, `LedgerKpis`, `LedgerTimelinePoint`, `LimitUsage`, `ReasonCount`, `CurrencyTotal`, `LedgerSummaryView`, `RunListItemView`, and `LedgerFilters(ApiModel)` (`period: str | None`, `tab: Literal["all","paid","escalated","stopped"] = "all"`, `payee_id: UUID | None`, `currency: str | None`), all exactly as defined in 03-design.
- `backend/modules/accountability/__init__.py`, `repository.py`, `service.py`, `csv_export.py`, `errors.py` (new).
- `backend/clients/accountability.py` (new).
- `backend/api/routers/accountability.py` (new):
  - `ledger_router = APIRouter(prefix="/ledger", tags=["ledger"])`
    - `GET /ledger/entries` (query params mirror `LedgerFilters`; `period` uses `PERIOD_PATTERN`) → `list[LedgerEntryView]`
    - `GET /ledger/summary?period=YYYY-MM&months=4` → `LedgerSummaryView`
    - `GET /ledger/export.csv` (same filters) → `Response(media_type="text/csv; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="agent-ledger-{period or all}.csv"'})`
  - `runs_router = APIRouter(prefix="/runs", tags=["runs"])`
    - `GET /runs?status=&limit=100` → `list[RunListItemView]`
- `backend/api/routers/payments.py`: add `GET /payments/runs/{run_id}/trace` → `RunTraceView`.
- `backend/contracts/payments.py`: add `TraceRole`, `TraceToolCall`, `TraceMessage` and `RunTraceView` (see 03-design).
- `backend/modules/payments/trace.py` (new): `serialize_messages(messages: list[BaseMessage]) -> list[TraceMessage]`.
- `backend/modules/payments/service.py`: `run_trace(owner, run_id) -> RunTraceView`.
- `backend/api/routers/__init__.py`: include `ledger_router` and `runs_router` with auth.

## Implementation Guidelines

### Ledger entries query (`AccountabilityRepository.ledger_entries(owner_id, filters) -> list[LedgerEntryRow]`)

The query is a `UNION ALL` of two selects, ordered by `occurred_at DESC` and capped at `LEDGER_ENTRY_LIMIT = 500`.

1. **Bill decisions**: `payment_decisions d JOIN bills b ON b.id = d.bill_id AND b.owner_id = :o`
   - `LEFT JOIN payees p ON p.id = b.payee_id`
   - `LEFT JOIN payments pay ON pay.bill_id = b.id`
   - `LEFT JOIN LATERAL (select source_type, inbox_email_id from bill_sources where bill_id = b.id order by created_at limit 1) s`
   - `LEFT JOIN inbox_emails e ON e.id = s.inbox_email_id` (for the subject)

   Selected columns:
   - Decision: `decision_id`, `created_at`, `actor`, `verdict`, `rule_results`, `explanation`, `note`, `run_id`
   - Bill: `b.*` amounts, FX fields, category, `b.status`, `b.duplicate_of_bill_id`
   - Payee: `p.display_name`, `p.kind`
   - Source: `s.source_type`, `e.subject`, `e.id`
2. **Inbox-only outcomes**: `inbox_emails e WHERE e.owner_id = :o AND e.status IN ('blocked','duplicate','no_invoice','no_info','error')` AND no bill decision is linked. In practice `e.run_id IS NULL`, or the run has no `bill_id`. Verify which condition holds for `no_invoice` and `no_info`, since those may have a run without a bill.

   Selected columns: `e.id`, `e.updated_at`, `e.status`, `e.violations`, `e.error`, `e.subject` and `e.provider`, mapped to the channel through `SOURCE_TYPE_BY_PROVIDER`.

Outcome mapping happens in the service, in a pure function `to_outcome(row) -> LedgerOutcome`:
- `actor=agent`: verdict `pay` → PAID. `review` → ESCALATED. `hold` → DUPLICATE when `rule_results` contains `DUP` and the bill has `duplicate_of_bill_id`; otherwise HELD.
- `actor=human`: verdict `pay` → APPROVED_BY_HUMAN. Anything else → REJECTED_BY_HUMAN.
- Inbox: blocked → BLOCKED, duplicate → DUPLICATE, no_invoice → NOT_AN_INVOICE, no_info → MISSING_INFO, error → ERROR.

Reasons:
- Decisions: the `rule_results` entries whose `effect != pass`.
- Blocked inbox items: each violation becomes `LedgerReason(rule_id="GUARD" or "MALWARE", name=violation.code, effect=HOLD, reason=violation.message)`. Check the actual violation codes the pipeline writes for malware and for the guardrail.

Explanation: the decision's `explanation`. For inbox rows, use a fixed English sentence per status, e.g. "Blocked before reaching the agent: prompt-injection attempt detected."

Filters:
- `period` matches `to_char(occurred_at, 'YYYY-MM')`.
- `tab` is applied after mapping, in Python (fine for 500 rows).
- `payee_id` and `currency` are applied in SQL.

`is_seeded = run_id is None and actor == agent and row came from decisions`.

### Summary (`AccountabilityService.summary(owner, period, months)`)

- **KPIs**: computed from the entries in `period`.
  - `paid_usd` sums `amount_usd` over PAID and APPROVED_BY_HUMAN.
  - `stopped_usd` sums `amount_usd` over HELD, REJECTED_BY_HUMAN and DUPLICATE, treating null as 0.
  - `auto_pay_rate` is the number of agent PAID entries divided by all agent bill decisions, or 0 when there are none.
- **Timeline**: entries from the last `months` months (default 4: three months of history plus the current one), bucketed by ISO week start `occurred_at.date() - timedelta(days=weekday)`, with counts per tab group. Emit empty buckets as zeros so the bars stay continuous.
- **Limits**: reuse `PaymentsClient.budget_usage(owner, period)`, which already returns `BudgetUsageView(scope, limit_usd, reserved_usd)` for each scope. Map each one to a `LimitUsage`, with the label resolved by `payee_id` from `PaymentPolicyClient.list_payees`, and include `payee_currency`. Sort payees by `spent/limit` descending, then categories, then global.
- **Top reasons**: count non-pass `rule_id` across the entries in the window, take the top 8, and take `name` from `RULE_NAMES`.
- **Currencies**: group PAID and APPROVED entries in `period` by `currency`, summing `amount`, `amount_usd` and `count`.

### Runs list (`AccountabilityRepository.list_runs(owner_id, status, limit)`)

```sql
select r.id, r.status, r.created_at, r.updated_at, r.error, r.bill_id,
       s.source_type, s.sender, e.id as inbox_email_id, e.subject,
       (select d.verdict from payment_decisions d where d.run_id = r.id order by d.created_at desc limit 1) as verdict,
       (select count(*) from agent_run_events ev where ev.run_id = r.id and ev.step = 'tool_finished') as tool_count
from agent_runs r
left join bill_sources s on s.id = r.bill_source_id
left join inbox_emails e on e.run_id = r.id
where r.owner_id = :o [and r.status = :status]
order by r.created_at desc limit :limit
```

Write it with SQLAlchemy Core rather than raw text. `duration_ms` is `(updated_at - created_at)` when the status is completed or failed; otherwise it is None.

### CSV (`csv_export.write_ledger_csv(entries) -> str`)

Use `csv.writer` over `io.StringIO` with these columns:

`occurred_at, outcome, actor, payee, payee_kind, category, amount, currency, amount_usd, fx_usd_per_unit, fx_rate_date, fx_source, reasons (" | "-joined "RID: reason"), explanation, human_note, channel, subject, bill_id, run_id`

Prefix any cell that starts with `= + - @` with `'` to prevent CSV formula injection, because subjects and reasons contain untrusted text.

### Trace (`PaymentsService.run_trace`, orientative)

```python
async def run_trace(self, owner: CurrentUser, run_id: UUID) -> RunTraceView:
    await self.get_run(owner, run_id)               # ownership check, raises RunNotFoundError
    checkpointer = self._dependencies.checkpointer
    if checkpointer is None:
        return RunTraceView(run_id=run_id, is_available=False, checkpoint_id=None, messages=[])
    checkpoint_tuple = await checkpointer.aget_tuple(thread_config(run_id))
    if checkpoint_tuple is None:
        return RunTraceView(run_id=run_id, is_available=False, checkpoint_id=None, messages=[])
    messages = checkpoint_tuple.checkpoint["channel_values"].get("messages", [])
    return RunTraceView(
        run_id=run_id,
        is_available=True,
        checkpoint_id=checkpoint_tuple.config["configurable"].get("checkpoint_id"),
        messages=serialize_messages(messages),
    )
```

`serialize_messages`:
- Maps `SystemMessage`, `HumanMessage`, `AIMessage` and `ToolMessage` to `TraceRole`.
- `text = message_text(message.content)`.
- For AI messages, `tool_calls = [TraceToolCall(call_id=c["id"], name=c["name"], args=c["args"])]`.
- For tool messages, sets `tool_call_id` and `tool_name=message.name`, and `output_json = json.loads(text)` when it parses (the tools return JSON strings).
- Skips other message types.

The deep agent's system prompt may not live in the checkpoint messages. If it is missing, prepend a `SYSTEM` `TraceMessage` built from `prompts.get(PromptId.PAYMENTS_AGENT)`, the same text `build_payments_agent` passes.

## Dependencies

- 02 (FX columns), 03 (English `RULE_NAMES`), `PaymentsClient.budget_usage`, `PaymentPolicyClient.list_payees`.

## Integration Notes

- 12 (ledger page) consumes `/ledger/entries`, `/ledger/summary` and `/ledger/export.csv`.
- 13 (runs pages) consumes `/runs`, `/payments/runs/{id}` (existing), `/bills/{bill_id}` (existing) and `/payments/runs/{id}/trace`.
