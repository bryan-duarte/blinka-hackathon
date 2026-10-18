# User Preferences & Decisions

## 👤 Configuration Preferences

- **Context Level**: Moderado
- **Participation Level**: Equilibrado
- **Detail Level**: Neutral (orientative snippets; implementer decides final code)

## 💬 Q&A and Rationale

### 🔐 Access

**Q:** The request cut off at the demo password. How should the evaluator password be set?
**A:** I set it in SSM.
**Decision:**
- Move `BLINKA_DEMO__PASSWORD` from `managed_params` to `operator_params` (`infra/ssm.tf`) with a `moved {}` block.
- Delete `random_password.demo_password` and `output "demo_password"`.
- The value is never written to git or to tfstate. The user writes it with `aws ssm put-parameter --overwrite`, then restarts. `ensure_user_with_password` re-hashes it on boot.
- Email stays `demo@blinka.dev`.
**Rejected:** Terraform random password: the user wants to choose the password.

**Q:** How tight should the lockdown be?
**A:** Demo-only console.
**Decision:**
- Remove `POST /demo/login`, `GET /demo/status`, `POST /auth/register` and the matching frontend UI.
- `/auth/login` and `get_current_user` reject any email other than `settings.demo.email` while `settings.demo.enabled`.
**Rejected:** Removing only the demo button: other users could still self-register and use the console.

### 📬 Integrations

**Q:** How should Gmail and Outlook scopes be narrowed?
**A:** Ignore for now; there is no time if it fails.
**Decision:** No change to the auth configs. Research findings are recorded in `05-risks.md` → "Deferred: OAuth scopes".
**Rejected:** N/A (deferred).

**Q:** How do evaluators use the WhatsApp sandbox (one active phone per owner)?
**A:** Keep a single phone.
**Decision:** No change to `register_whatsapp_sandbox` or `expire_sandbox_connections`. The operator checklist has the user register their own phone last.
**Rejected:** Multiple phones per demo user: not wanted.

**Q:** How should connection-state freshness be handled?
**A:** Reconcile on read.
**Decision:** `InboxService.list_connections` refreshes active Gmail/Outlook rows from Composio, using an in-memory TTL cache (60s), and stores the new status. The verification script is still added for the one-off prod check.
**Rejected:** Verification script only: the UI would keep showing stale "active" rows.

### ⚙️ Concurrency

**Q:** Which queueing model?
**A:** DB-backed queue.
**Decision:**
- `agent_runs.status='pending'` and `inbox_emails.status='received'` act as the queue.
- Workers claim rows with `FOR UPDATE SKIP LOCKED`, gated by a semaphore. An `asyncio.Event` wakes them, with a poll fallback.
- The inbox source payload is persisted to a new `inbox_emails.source_payload` JSONB column.
**Rejected:** In-process semaphore: queued work is lost on restart. SQS: extra infrastructure and local-dev friction.

**Q:** Which limits?
**A:** 8 runs, demo 20.
**Decision:**
- `BLINKA_WORKERS__AGENT_RUN_CONCURRENCY=8` and `BLINKA_WORKERS__INBOX_CONCURRENCY=8`.
- `BLINKA_DEMO__MAX_RUNNING_LAUNCHES=20`.
- SQLAlchemy `pool_size=10`, `max_overflow=10`.
- The checkpointer moves to an `AsyncConnectionPool` (max 10).
**Rejected:** 4 runs / demo 10 is too slow for the demo. 16 runs / demo 30 would starve the t4g.micro.

### 💸 Idempotency

**Q:** Which settlement gaps should be fixed?
**A:** Only the critical one.
**Decision:** Fix only the `settle` ordering. The bill compare-and-set, the reserve, the execute and the decision insert are committed in one transaction, through `LedgerRepository.commit_settlement`.
**Rejected:** Fixing all gaps (atomic reject, decision uniqueness, per-bill advisory lock): out of scope by user choice. They are recorded as residual risks.

### 📡 Events & Visualization

**Q:** Which richer events?
**A:** All four:
- pipeline stages
- rule-by-rule stream
- extraction and checker detail
- tool output plus LLM metadata
**Decision:**
- New realtime types: `pipeline.stage`, `agent.rule`, `agent.llm`.
- Payloads are projected per step instead of the global allowlist.
- New run steps: `checker_answered` and `fx_converted`.
**Rejected:** N/A.

**Q:** Where should the visualization show up?
**A:** Inbox panel and the live run page.
**Decision:** Upgrade `AgentActivity`. `/runs/[id]` subscribes to `useInboxChannel` filtered by `run_id`, and keeps polling only while offline.
**Rejected:** Inbox only is too narrow. A new full-screen view is extra surface.

### 🗄️ Database & Audit

**Q:** How should the DBs be separated?
**A:** A separate RDS instance.
**Decision:**
- New `aws_db_instance.agent` (`blinka-prod-agent`, db `blinka_agent`) for LangGraph checkpoints only.
- Code rename:
  - `payments_database_url` → `agent_database_url` (env `BLINKA_AGENT_DATABASE_URL`)
  - `Pools.payments` → `Pools.agent`
  - `PaymentsBase` → `AgentBase`
  - Alembic section `payments` → `agent`
- Old checkpoints are **not** migrated.
**Rejected:** Renaming only: the user explicitly wants physical separation.

**Q:** Which instances get pgaudit?
**A:** Both.
**Decision:** One shared `aws_db_parameter_group.audit` (family `postgres17`) attached to both instances.

**Q:** What are the "automatic copies in S3"?
**A:** Audit logs to S3.
**Decision:** RDS `enabled_cloudwatch_logs_exports=["postgresql"]`, then a CloudWatch subscription filter on `AUDIT:`, then one Firehose stream per instance, landing in `blinka-db-audit-<account_id>` (versioned, SSE, lifecycle).
**Rejected:** Snapshot exports: not requested.

**Q:** What pgaudit scope?
**A:** Instance-wide `ddl,write,role`.
**Decision:** `pgaudit.log=ddl,write,role`, `pgaudit.log_catalog=0`, `pgaudit.log_parameter=0`. `CREATE EXTENSION pgaudit` runs through a guarded Alembic migration in both chains.
**Rejected:** `all`: read volume is too high on a t4g.micro.

### 🤖 Agent-decided (not asked)

- **Demo sequencer:** `STEP_TIMEOUT_SECONDS` goes from 150 to 300, because queued steps can now wait for a worker.
- **Startup recovery:** `fail_unfinished` only fails `running` runs and `processing`/`analyzing` inbox items. `pending` runs and `received` emails stay queued and are processed after the restart.
- **Landing page:** the CTAs (`/login?mode=register`) now point to `/login`.
- **Tool call ids:** live tool events carry the LLM `tool_call_id` when the event exposes it, so they can be joined to the trace. Otherwise they fall back to the LangGraph `run_id`.
