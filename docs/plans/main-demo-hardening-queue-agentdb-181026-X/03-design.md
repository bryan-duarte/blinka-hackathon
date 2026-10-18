# Technical Design

## Architecture Decisions

1. **Single-tenant console while demo mode is on.**
   - `settings.demo.enabled` is the switch. When it is on, `get_current_user` and `AuthService.login` accept only `settings.demo.email`.
   - A wrong email returns the same `InvalidCredentialsError` as a wrong password, so it cannot be used to enumerate accounts.
   - JWTs that other users already hold get a 401.
2. **Connection truth = DB, refreshed from Composio on read.**
   - `InboxService.list_connections` calls `mail_gateway.get_account_status` for each `gmail`/`outlook` row whose status is `active` and whose last check is older than 60s.
   - The last-check time lives in an in-memory `dict[UUID, float]` on the service. Single instance: no migration needed.
   - If Composio errors, keep the DB status and log `mailbox_reconcile_failed`.
3. **Settlement commits atomically.**
   - `settle()` decides the verdict and builds the decision.
   - `LedgerRepository.commit_settlement(...)` then runs **one** transaction: `UPDATE bills ... WHERE status IN (from_status)` (CAS), then the payment insert, the counter charges and the execute, then the decision insert.
   - On a CAS miss it rolls back and raises `BillStateConflictError`, so no money moves.
   - On budget exhaustion it rolls back and raises `BudgetExhaustedError`. The caller downgrades the verdict to HOLD (rule R14 blocker) and commits again with no reservation.
   - This deliberately touches `BillRow` from the payments module (both are in the product DB). It is the only cross-module write, and it is commented with the reason.
4. **Postgres-backed work queue, no new infrastructure.**
   - A generic `core/work_queue.py` `QueueWorker` claims IDs with `UPDATE ... RETURNING` over a `FOR UPDATE SKIP LOCKED` subselect.
   - It runs each claimed ID under `asyncio.Semaphore(concurrency)` and hands the task to the existing `ExecutionRegistry`, so `cancel_owner` and `shutdown` keep working.
   - Producers call `worker.notify()` after their insert commits.
5. **Events: per-step payload projection replaces the global allowlist.** `REALTIME_PAYLOAD_KEYS` is deleted. Each recorder method builds its realtime payload explicitly, capped at `REALTIME_PAYLOAD_MAX_BYTES = 16_000`, with string fields truncated. The DB stores the full payload, as today.
6. **Agent DB is a separate RDS instance holding only checkpoints.** There is no data migration: old runs' traces return `is_available=false`, which the UI already handles.
7. **pgaudit on both instances through one shared parameter group.** Logs go from CloudWatch to S3 through Firehose, one stream per instance, keyed by `for_each`.

## Patterns & Conventions

- **Layering:** contracts → clients → modules → `container.py`. New settings go in `core/config.py` as a nested `BaseSettings` group with `env_prefix="BLINKA_<GROUP>__"`. Mirror `DemoSettings` (`core/config.py:132-147`).
- **Errors:**
  - Each domain error subclasses the module's base error and is mapped in `DOMAIN_ERROR_RESPONSES` (`api/app.py:66-106`).
  - Services never raise `HTTPException`. Only `api/deps.py` does.
- **Logging:** use `get_logger(__name__)` with snake_case event names and fields as kwargs (e.g. `logger.info("queue_claimed", queue="agent_runs", count=n)`).
- **Repository upserts:** use `insert(...).on_conflict_do_nothing(...)`, and conditional `update(...).where(status.in_(...)).returning(...)` for compare-and-set (see `modules/bills/repository.py:117-139`).
- **Constants:** every literal is an UPPER_SNAKE module constant. Private helpers are `_snake` functions at the bottom of the module.
- **Frontend:**
  - Local `useState`/`useEffect` with `isCancelled` cleanup.
  - All API calls go through the single `api` object in `lib/api.ts`.
  - Tailwind class constants. Follow `frontend/DESIGN.md` (ink-on-marble: ink tokens only, iris only for chart strokes and link hover, 1px hairlines, no shadows).
  - Load the `frontend-design` skill before UI edits.
- **Terraform:** a flat root module. `local.name` / `local.env` naming. Operator-owned SSM params go in `operator_params` with `ignore_changes = [value]`.

## Dependencies

- No new Python packages. `psycopg_pool` already ships as a dependency of `langgraph-checkpoint-postgres`. Verify with `uv pip show psycopg-pool`. If it is missing, add it with `uv add psycopg-pool`, never by hand-editing files.
- No new npm packages.
- Terraform AWS provider `>= 6.9, < 7.0` (existing). Resources used:
  - `aws_db_parameter_group`
  - `aws_kinesis_firehose_delivery_stream`
  - `aws_cloudwatch_log_subscription_filter`
  - `aws_cloudwatch_log_group`
  - `aws_s3_bucket*`

## Integration Points

| Change | Exact location |
|---|---|
| Remove public demo routes | `backend/api/routers/demo.py:12-23` (`demo_public_router`), `backend/api/routers/__init__.py:25` |
| Remove register | `backend/api/routers/auth.py:9-11`, `backend/modules/auth/service.py:23` (`register`), `backend/clients/auth.py` (`register`) |
| Demo-only guard | `backend/api/deps.py:28-45` (`get_current_user`), `backend/modules/auth/service.py:29` (`login`) |
| Reconcile connections | `backend/modules/inbox/service.py:184-189` (`list_connections`), `backend/modules/mail_gateway/service.py:105-113` (`get_account_status`) |
| Atomic settle | `backend/modules/payments/settlement.py:55-92` (`settle`), `:189-229` (`_pay`), `backend/modules/payments/ledger_repository.py:59-149` |
| Queue: runs | `backend/modules/payments/service.py:89-110` (`start_run` spawn → notify), `backend/modules/payments/runner.py:32` (`run_execution`) |
| Queue: inbox | `backend/modules/inbox/service.py:302-310` (`_accept` spawn → persist source + notify), `backend/modules/inbox/pipeline.py:68` (`process_email`) |
| Recovery | `backend/api/app.py:118-120`, `backend/modules/payments/repository.py:162-172` (`fail_unfinished`), inbox `fail_unfinished` |
| Worker lifecycle | `backend/api/app.py` `lifespan` (start after recovery, stop before registries shutdown), `backend/container.py:83+` (`build_clients`) |
| Demo cap | `backend/modules/demo/service.py:56-57`, `backend/modules/demo/sequencer.py:31` |
| Events | `backend/modules/payments/events.py`, `backend/modules/payments/agent.py:60-95`, `backend/modules/payments/agent_tools.py:132-337`, `backend/modules/inbox/notifier.py:16-35`, `backend/modules/inbox/pipeline.py:76-135` |
| Realtime contract | `backend/contracts/realtime.py`, `frontend/src/lib/types.ts:334-357` |
| DB split | `backend/core/config.py:164`, `backend/core/db/{engine,base,checkpointers,bootstrap,__init__}.py`, `backend/alembic.ini:5-17`, `backend/alembic/env.py:13-28`, `backend/docker-entrypoint.sh`, `backend/scripts/seed_demo.py:22-39`, `docker-compose.yml`, `backend/.env.example` |
| Infra | `infra/database.tf`, `infra/ssm.tf:25-67`, `infra/outputs.tf`, new `infra/audit.tf` |

## Data Structures

### New / changed columns (product DB, one Alembic migration)

```text
inbox_emails.source_payload   JSONB NULL   -- serialized InboxSource: {"kind": "mail_trigger"|"whatsapp_document"|"fetched_email", "data": {...model_dump(mode="json")}}
inbox_emails.pipeline_stages  JSONB NOT NULL DEFAULT '[]'  -- appended PipelineStageRecord list
ix_inbox_emails_status_created  (status, created_at)  -- queue scan
ix_agent_runs_status_created    (status, created_at)  -- queue scan
```

### Settings (`core/config.py`)

```python
class WorkerSettings(BaseSettings):   # env_prefix="BLINKA_WORKERS__"
    agent_run_concurrency: int = 8
    inbox_concurrency: int = 8
    poll_interval_seconds: float = 2.0
    db_pool_size: int = 10
    db_max_overflow: int = 10
    checkpointer_pool_size: int = 10

class DemoSettings:  # add
    max_running_launches: int = 20

class Settings:      # rename
    agent_database_url: str           # was payments_database_url; env BLINKA_AGENT_DATABASE_URL
    workers: WorkerSettings = WorkerSettings()
```

### Realtime contract (`contracts/realtime.py` + `frontend/src/lib/types.ts`)

```python
class RealtimeEventType(StrEnum):
    INBOX_ITEM = "inbox.item"
    PIPELINE_STAGE = "pipeline.stage"   # new
    RUN_STEP = "run.step"
    AGENT_TOOL = "agent.tool"
    AGENT_TODOS = "agent.todos"
    AGENT_THINKING = "agent.thinking"
    AGENT_RULE = "agent.rule"           # new
    AGENT_LLM = "agent.llm"             # new
```

The `RealtimeEvent` shape is unchanged. New payloads (realtime projection):

| type / step | payload |
|---|---|
| `pipeline.stage` / `<stage>` where stage ∈ `fetch, attachments, malware_scan, guardrail, dedup, queued, handoff` | `{stage, status: "started"\|"finished"\|"failed", duration_ms?, detail?: {files?, scan_status?, guardrail_action?, violations?, duplicate?}}` |
| `run.step` / `classified` | `{is_bill, kind, confidence, reason}` |
| `run.step` / `extracted` | `{method, document_origin, fields: [{name, value, confidence}]}` (payee, invoice_number, amount, currency, due_date, category) |
| `run.step` / `fx_converted` (new) | `{amount, currency, amount_usd, usd_per_unit, rate_date, source}` |
| `run.step` / `claimed` | `{bill_id, duplicate_of?}` |
| `agent.rule` / `rule_evaluated` (new) | `{code, name, outcome: "pass"\|"flag"\|"review"\|"hold", detail, evidence (≤1KB)}` |
| `run.step` / `rules_evaluated` (new) | `{provisional_verdict, passed_count, flagged_count}` |
| `run.step` / `checker_answered` (new) | `{answers: [{question, probability, rationale}], verdict_after_checker}` |
| `agent.tool` / `tool_finished` | adds `summary` (≤1000 chars) |
| `agent.llm` / `llm_call` (new) | `{node, parent_tool?, model, input_tokens, output_tokens, duration_ms}` |
| `run.step` / `decided` | `{verdict, bill_id, explanation}` |
| `run.step` / `failed` | `{error}` |

```ts
// frontend/src/lib/types.ts (additions)
export type RuleOutcome = "pass" | "flag" | "review" | "hold";
export type PipelineStageStatus = "started" | "finished" | "failed";
export interface PipelineStagePayload { stage: string; status: PipelineStageStatus; duration_ms?: number; detail?: Record<string, unknown> }
export interface RuleEventPayload { code: string; name: string; outcome: RuleOutcome; detail: string; evidence?: Record<string, unknown> }
export interface LlmCallPayload { node: string; parent_tool?: string; model: string; input_tokens: number; output_tokens: number; duration_ms: number }
```

### Ledger settlement API (`modules/payments/ledger_repository.py`)

```python
async def commit_settlement(
    self,
    bill_ref: BillRef,                      # owner_id, bill_id
    from_statuses: tuple[BillStatus, ...],
    target_status: BillStatus,
    reservation: ReservationRequest | None, # None for HOLD/REVIEW
    decision: DecisionRecord,
) -> DecisionRecord: ...
# raises BillStateConflictError (CAS miss) | BudgetExhaustedError (counter over limit); both roll back fully
```

### Infra resources

```text
aws_db_parameter_group.audit            family=postgres17, shared by main + agent
aws_db_instance.agent                   blinka-prod-agent, db_name=blinka_agent, t4g.micro, gp3 20GB, encrypted
random_password.agent_db                32 chars, no special
aws_cloudwatch_log_group.rds["main"|"agent"]   /aws/rds/instance/<id>/postgresql, retention 30d
aws_s3_bucket.db_audit                  blinka-db-audit-<account_id>, versioned, AES256, public block, lifecycle
aws_kinesis_firehose_delivery_stream.db_audit["main"|"agent"]
aws_cloudwatch_log_subscription_filter.db_audit["main"|"agent"]  filter_pattern="AUDIT"
aws_iam_role.firehose_db_audit, aws_iam_role.cwl_to_firehose
```
