# Implementation Tasks

## Task Breakdown

### 1. Demo access lockdown → `06-implementation/01-demo-access-lockdown`
- [x] Remove `demo_public_router` (`GET /demo/status`, `POST /demo/login`), `DemoService.login`, `DemoClient.login` and `DemoStatusView`
- [x] Remove `POST /auth/register`, `AuthService.register` and `AuthClient.register`
- [x] Make `get_current_user` and `AuthService.login` accept only `settings.demo.email` while demo mode is enabled
- [x] Frontend: delete `DemoEntry`, the register mode/toggle, and `api.register` / `demoStatus` / `demoLogin` along with their types
- [x] Point the landing CTAs at `/login`
- [x] Infra: move `BLINKA_DEMO__PASSWORD` to `operator_params` (with a `moved` block) and delete `random_password.demo_password` and `output.demo_password`
- [x] Update the `.env.example` demo comment

### 2. Demo integrations state → `06-implementation/02-demo-integrations-state`
- [x] Reconcile Gmail/Outlook status from Composio in `InboxService.list_connections` (60s TTL)
- [x] Add `backend/scripts/check_demo_integrations.py`, which prints the demo user's connections, Composio status, trigger presence and Kapso sandbox config
- [ ] Run the operator checklist in prod: set the SSM values, deploy, log in as demo, connect Gmail and Outlook, register the sandbox phone, run the check script _(operator step after deploy; not run by the implementer)_

### 3. Settlement atomicity → `06-implementation/03-settlement-atomicity`
- [x] Add `LedgerRepository.commit_settlement` (bill CAS, reserve, execute and decision in one transaction)
- [x] Rewrite `settle()` / `_pay()` to use it, downgrading to HOLD on `BudgetExhaustedError`
- [x] Keep `recover_unfinished_payments` for legacy RESERVED rows

### 4. Durable run queue → `06-implementation/04-durable-run-queue`
- [x] Add `WorkerSettings` and `DemoSettings.max_running_launches`
- [x] Add the migration: `inbox_emails.source_payload`, `pipeline_stages`, and the queue indexes
- [x] Add `core/work_queue.py` (`QueueWorker`)
- [x] Add claim queries to the runs and inbox repositories
- [x] Rewire `start_run` and `_accept` to enqueue and notify
- [x] Start and stop the workers in `lifespan`
- [x] Change `fail_unfinished` so it only fails in-flight statuses
- [x] Set the engine `pool_size` / `max_overflow` and move the checkpointer to `AsyncConnectionPool`
- [x] Demo: raise the cap to 20 (from settings) and the step timeout to 300s

### 5. Rich agent events (backend) → `06-implementation/05-rich-agent-events`
- [x] Add the `PIPELINE_STAGE`, `AGENT_RULE` and `AGENT_LLM` types
- [x] Replace `REALTIME_PAYLOAD_KEYS` with per-step projection and a size cap
- [x] Emit pipeline stage events from the inbox pipeline and persist them to `inbox_emails.pipeline_stages`
- [x] Emit `rule_evaluated`, `rules_evaluated`, `fx_converted` and `checker_answered` from the agent tools
- [x] Emit `agent.llm` for every chat model end (including calls nested inside tools), with tokens and duration
- [x] Include `summary` (up to 1000 chars) in `tool_finished`, and use the LLM `tool_call_id` when available
- [x] Expose `pipeline_stages` on `InboxEmailDetail` and `PaymentRunStatus`

### 6. Agent visualization (frontend) → `06-implementation/06-agent-visualization`
- [x] Extend the types and `lib/runEvents.ts` selectors (stages, rules, extraction, fx, checker, LLM calls)
- [x] Upgrade `AgentActivity`: stage rail, live rule grid, extracted-fields card, checker meters, token/latency footer
- [x] `/runs/[id]`: subscribe to realtime filtered by `run_id`, poll only while offline, and feed `RunTimeline` from live events
- [x] Route the new event types in `inbox/page.tsx`

### 7. Agent DB split → `06-implementation/07-agent-db-split`
- [x] Rename `payments_database_url` → `agent_database_url`, `Pools.payments` → `Pools.agent`, `PaymentsBase` → `AgentBase`, and the Alembic section `payments` → `agent` (move the versions folder)
- [x] Update `docker-entrypoint.sh`, `seed_demo.py`, `docker-compose.yml` and `.env.example`
- [x] Infra: add `aws_db_instance.agent` and `random_password.agent_db`; SSM `BLINKA_AGENT_DATABASE_URL` replaces `BLINKA_PAYMENTS_DATABASE_URL`
- [ ] After the cutover is verified, manually `DROP DATABASE blinka_payments` on the main instance _(operator step after deploy; not run by the implementer)_

### 8. PGAudit + S3 → `06-implementation/08-pgaudit-s3`
- [x] Add `aws_db_parameter_group.audit` and attach it to both instances
- [x] Enable `postgresql` log exports and add managed log groups with 30-day retention
- [x] Add the S3 audit bucket, the Firehose streams, the subscription filters and the IAM roles (new `infra/audit.tf`)
- [x] Add a guarded `CREATE EXTENSION IF NOT EXISTS pgaudit` migration to the product and agent chains
- [ ] Reboot both instances once, then verify `SHOW shared_preload_libraries` and that objects arrive in S3 _(operator step after deploy; not run by the implementer)_

### Post-Implementation Quality Gate
- [ ] Run a two-subagent quality pass over the recently-applied change:
  - [ ] **Bug sweep:** launch a subagent to search the modified code for bugs, issues and inconsistencies (logic errors, edge cases, broken contracts, dead code, regressions). Report concrete findings as `file:line` references.
  - [ ] **Polish:** launch a subagent that invokes the `codebase-change` skill and applies the polish DIRECTLY to the changed files. It deletes unnecessary comments, makes the code self-explanatory, gives every variable an obvious purpose, maximizes readability and maintainability, and removes unnecessary complexity. It also resolves any real issues the bug sweep surfaced.

## Task Order

```
 7 Agent DB split ──┬──▶ 8 PGAudit + S3 (needs both instances)
                    └──▶ 4 Queue (checkpointer pool on new agent URL)
 3 Settlement ─────────▶ (independent, before 4 is safest)
 4 Queue ──────────────▶ 5 Events (pipeline stages hook into queued pipeline)
 5 Events ─────────────▶ 6 Visualization
 1 Lockdown ───────────▶ 2 Integrations (operator checklist runs last, after deploy)
```

Deploy once at the end. `deploy.sh` runs the migrations; after `terraform apply`, reboot both RDS instances for `shared_preload_libraries`. Then run the operator checklist in module 2.
