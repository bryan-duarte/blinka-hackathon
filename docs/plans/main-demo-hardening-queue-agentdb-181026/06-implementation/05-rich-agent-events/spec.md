# Rich Agent Events (Backend) Implementation

## Overview

Stream a much richer execution trace to the frontend:
- pre-agent pipeline stages
- one event per policy rule
- extraction fields with confidence
- FX conversion
- checker answers
- tool output summaries
- every LLM call (including calls nested inside tools), with model, tokens and latency

Everything except `agent.thinking` and `pipeline.stage` is persisted in `agent_run_events`. Pipeline stages are persisted to `inbox_emails.pipeline_stages`.

## Files to Modify/Create

- `backend/contracts/realtime.py`: add `PIPELINE_STAGE = "pipeline.stage"`, `AGENT_RULE = "agent.rule"` and `AGENT_LLM = "agent.llm"` to `RealtimeEventType`.
- `backend/contracts/inbox.py`: add the `PipelineStageRecord` model (`stage: str, status: Literal["started","finished","failed"], duration_ms: int | None, detail: dict, at: datetime`). Add `pipeline_stages: list[PipelineStageRecord] = []` to `InboxEmailDetail`.
- `backend/contracts/payments.py`: add `pipeline_stages: list[PipelineStageRecord] = []` to `PaymentRunStatus` (lines 194-202). Fill it from the run's `inbox_email` when one exists.
- `backend/modules/payments/events.py`:
  - delete `REALTIME_PAYLOAD_KEYS` and `_realtime_payload`, and add `_cap_payload(payload) -> dict`;
  - add the step constants `RULE_EVALUATED_STEP`, `RULES_EVALUATED_STEP`, `FX_CONVERTED_STEP`, `CHECKER_ANSWERED_STEP` and `LLM_CALL_STEP`;
  - raise `TOOL_SUMMARY_MAX_CHARS` from 280 to 1000;
  - add `rules(results, provisional_verdict)` and `llm_call(...)`;
  - `step()` accepts a `realtime_payload` override.
- `backend/modules/payments/repository.py`: add `insert_events(run_id, events: list[tuple[str, dict]]) -> list[PaymentRunEvent]` (bulk insert with `RETURNING`) for the rule batch.
- `backend/modules/payments/agent_tools.py`:
  - `_classify` (line ~140): emit `classified` with `{is_bill, kind, confidence, reason}`.
  - `_extract` (lines ~178-186): emit `extracted` with `{method, document_origin, fields:[{name, value, confidence}]}`, built from the candidate's per-field evidence/confidence.
  - `_register_bill` (lines 203-239): after the claim, emit `fx_converted` when `amount_usd` is present (`{amount, currency, amount_usd, usd_per_unit, rate_date, source}`).
  - `_evaluate_rules` (lines ~250-276): call `events.rules(evaluation.results, evaluation.verdict)`.
  - `_run_checker` (lines ~285-305): emit `checker_answered` with `{answers:[{question, probability, rationale}], verdict_after_checker}`.
  - `_settle_decision` (lines 307-337): `decided` adds `explanation`.
- `backend/modules/payments/agent.py` `stream_agent` (lines 60-95):
  - track `on_chat_model_start` by `event["run_id"]`, then emit `llm_call` on `on_chat_model_end` for **all** chat models (drop the `is_agent_model_event` filter for this branch only);
  - pass `tool_call_id` when available.
- `backend/modules/inbox/notifier.py`: add `stage(owner_id, email_id, stage, status, duration_ms=None, detail=None)`, which publishes `pipeline.stage` and appends to `pipeline_stages` through the repository.
- `backend/modules/inbox/repository.py`: add `append_stage(email_id, record: dict)` using `pipeline_stages = pipeline_stages || :record::jsonb`.
- `backend/modules/inbox/pipeline.py` (lines 76-135): wrap each stage with a small timing helper. The stages are `fetch`, `attachments`, `malware_scan`, `guardrail`, `dedup` and `handoff`.
- `backend/modules/inbox/service.py`:
  - `_accept` emits the `queued` stage;
  - `get_email` / detail mapping includes `pipeline_stages`.
- `backend/modules/payments/phrases.py`: add human phrases for the new steps (follow the existing `pick_step_phrase` tables).

## Implementation Guidelines

```python
# events.py (orientative)
REALTIME_PAYLOAD_MAX_BYTES = 16_000
EVIDENCE_MAX_CHARS = 1_000

async def rules(self, results: Sequence[RuleResult], provisional_verdict: Verdict) -> None:
    rule_events = [(RULE_EVALUATED_STEP, _rule_payload(result)) for result in results]
    flagged_count = sum(1 for r in results if r.effect is not RuleEffect.PASS)
    rule_events.append((RULES_EVALUATED_STEP, {
        "provisional_verdict": provisional_verdict,
        "passed_count": len(results) - flagged_count,
        "flagged_count": flagged_count,
    }))
    stored = await self._repository.insert_events(self._run_id, rule_events)
    await self._publish_many([
        (RealtimeEventType.AGENT_RULE if e.step == RULE_EVALUATED_STEP else RealtimeEventType.RUN_STEP, e)
        for e in stored
    ])

async def llm_call(self, node: str, parent_tool: str | None, model: str,
                   input_tokens: int, output_tokens: int, duration_ms: int) -> None:
    stored = await self._repository.insert_event(self._run_id, LLM_CALL_STEP, {...})
    await self._publish(RealtimeEventType.AGENT_LLM, stored, None)

def _cap_payload(payload: dict) -> dict:
    encoded = json.dumps(payload, default=str)
    if len(encoded.encode()) <= REALTIME_PAYLOAD_MAX_BYTES:
        return payload
    return {k: (v[:EVIDENCE_MAX_CHARS] if isinstance(v, str) else v) for k, v in payload.items()
            if k not in {"evidence", "summary", "fields"}} | {"truncated": True}
```

- **Rule mapping.** `_rule_payload(result)` maps `RuleResult` (`modules/payments/rules.py:107-145`) to `{code, name: RULE_NAMES[code], outcome, detail, evidence}`.
  - `outcome` maps from `RuleEffect`: PASS → `pass`, FLAG → `flag`, REVIEW → `review`, HOLD → `hold`. Check the exact enum members.
  - Evidence is serialized with `mode="json"` and trimmed to 1KB.
- **Publishing.** `_publish_many` sends one `realtime.publish` call with a list; the realtime service already batches in groups of 5.
- **LLM metadata from `astream_events` v2:**
  - `event["metadata"].get("langgraph_node")` gives the node; `event["metadata"].get("ls_model_name")` gives the model.
  - `event["data"]["output"].usage_metadata` (an `AIMessage`) has `input_tokens` and `output_tokens`.
  - `parent_tool` is the closest step tool among `event["parent_ids"]`. Keep a `run_id → tool name` map filled on `on_tool_start`.
  - Nested calls (classification, extraction, checker) only show up in the stream if those tool implementations invoke the model with the callbacks of the current run config. Verify this. If nested calls do not show up, propagate `config` through `PaymentStepTools`, or emit `llm_call` directly from `llm_gateway` through a context-var recorder. Choose the smaller change.
- **Tool call id.** In `on_tool_start`, read `event["data"]["input"]` / `event["metadata"]` for the LLM `tool_call_id`; LangGraph's ToolNode includes it in the tool call config in recent versions. Fall back to `event["run_id"]`. Use the same id in `tool_started` and `tool_finished`.
- **Pipeline stage helper:**

```python
@asynccontextmanager
async def _stage(notifier, owner_id, email_id, stage: str, detail: dict | None = None):
    started_at = monotonic()
    await notifier.stage(owner_id, email_id, stage, "started")
    try:
        yield (stage_detail := dict(detail or {}))
    except Exception:
        await notifier.stage(owner_id, email_id, stage, "failed", _elapsed_ms(started_at), stage_detail)
        raise
    await notifier.stage(owner_id, email_id, stage, "finished", _elapsed_ms(started_at), stage_detail)
```

- Persist only `finished` and `failed` records to `pipeline_stages`; `started` is realtime-only, to keep the JSONB small.
- Stage `detail` fields:
  - `files` (count)
  - `scan_status` (from `FileScanStatus`)
  - `guardrail_action` / `violations` (from the guardrail result)
  - `duplicate: bool`

## Dependencies

- Module 04: the `inbox_emails.pipeline_stages` column and the queued `_accept`.
- Existing `RealtimeClient.publish(owner_id, events: list[RealtimeEvent])`.

## Integration Notes

- **Frontend contract:** type and step names and payload shapes exactly as in the `03-design.md` table, mirrored in `frontend/src/lib/types.ts` (module 06).
- **`sequence`:** stays `agent_run_events.id` for persisted events. `pipeline.stage` and `agent.thinking` send `sequence=None`, and the frontend dedups them by `(step, payload.status, created_at)`.
- **Run status endpoint:** `GET /payments/runs/{id}` already returns all persisted events, so the run page gets rules, LLM calls and everything else on first load.
