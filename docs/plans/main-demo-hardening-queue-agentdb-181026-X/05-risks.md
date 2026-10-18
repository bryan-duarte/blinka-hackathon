# Risks & Mitigations

## Technical Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| The reboot needed for `shared_preload_libraries` takes the product DB down for about 1-3 minutes | med | Reboot once, before evaluators get access. Stop the ECS service first (`desired_count 0`) and redeploy afterwards. |
| pgaudit `write` on the agent DB logs every checkpoint INSERT, which makes CloudWatch and Firehose volume high | med | `pgaudit.log_parameter=0` and `log_catalog=0`, and a subscription filter on `AUDIT`. If volume is still high, set `pgaudit.log='ddl,role'` on the agent DB only with `ALTER DATABASE blinka_agent SET pgaudit.log`. |
| Local `postgres:17-alpine` has no pgaudit, so the migration would fail locally | med | The migration only runs `CREATE EXTENSION` when `pg_available_extensions` lists `pgaudit`. |
| Old LangGraph checkpoints stay on the main instance, so old runs lose their trace view | low | The UI already handles `is_available=false`. Seeded demo history has no checkpoints. Drop `blinka_payments` after the cutover. |
| Settlement now touches `BillRow` from the payments module (crosses a module boundary) | low | Isolated in a single function `commit_settlement`, with a one-line comment explaining why. |
| `FOR UPDATE SKIP LOCKED` claims work across instances, but startup recovery (`fail_unfinished`, `stuck_bills`) still assumes a single task | med | Keep `desired_count=1` and stop-then-start deploys (current). Revisit if autoscaling is added. |
| 8 concurrent agent runs plus 8 pipelines on a db.t4g.micro and a 1 vCPU task cause pool or LLM throttling | med | All limits come from env (`BLINKA_WORKERS__*`). Pool is 10+10. The checkpointer uses a pool of 10. Lower the limits through SSM without a code change. |
| Demo sequencer steps time out while queued | low | `STEP_TIMEOUT_SECONDS` goes to 300. Demo cap is 20 launches. |
| Realtime event volume rises (16 rule events plus LLM events per run) | low | Publishing already batches 5 events per call. Payloads are capped at 16KB. Thinking stays realtime-only. |
| A Composio reconcile on every `GET /inbox/connections` adds latency or fails | low | 60s TTL per connection, `asyncio.gather` across rows, and the DB status is kept on error. |

## Integration Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Moving the demo password into `operator_params` resets it to `assign_later`, so the demo login breaks until it is set | high | A `moved {}` block keeps the current value. Then run `aws ssm put-parameter --overwrite` with the new password and `deploy.sh --restart`. |
| Existing non-demo JWTs (e2e users) stop working | low | Intended. They get a 401 and are sent to `/login`. |
| The prod demo user has no Gmail/Outlook/WhatsApp connection yet. Only local dev has Gmail and Outlook active; local has no WhatsApp row for demo, and prod is unverified because AWS creds expired during planning | high | Run the operator checklist and `check_demo_integrations.py` in prod after the deploy. |
| Evaluators share one demo account. If an evaluator registers their own phone in the sandbox, it expires yours (single-phone choice) | med | Accepted by the user. Re-register your phone after evaluations if needed. |
| `BLINKA_KAPSO__SANDBOX_*` and `BLINKA_COMPOSIO__*_AUTH_CONFIG_ID` SSM values still set to `assign_later` | high | The checklist checks `deploy.sh`'s `assign_later` warning, and the check script prints whether each setting is configured. |
| Renaming the env var `BLINKA_PAYMENTS_DATABASE_URL` → `BLINKA_AGENT_DATABASE_URL` breaks local `.env` | low | Update `.env.example`. The local override uses `blinka-dev-payments` on 55434 (rename the container, or just point the new var at it). |

## Residual (accepted, not fixed by user choice)

- `reject` flips the bill to REJECTED before writing the HOLD decision. A crash in between leaves a REJECTED bill with no decision.
- `payment_decisions` has no uniqueness constraint, so a recovery path can append a second decision.
- `payments.version` / `bills.version` are bumped but never used as a guard.

## Deferred: OAuth scopes (research, kept for later)

- **Current state:**
  - The managed configs `ac_PGfjAt0BW2PN` (Gmail) and `ac_s0yi7UV5o_OS` (Outlook) use Composio's defaults.
  - Gmail requests `https://mail.google.com/` (full mailbox) plus 10 People/userinfo scopes.
  - Outlook requests Mail.Send, Mail.ReadWrite, Calendars.*, Contacts.ReadWrite and Chat.ReadWrite.
- **Minimum needed:**
  - Gmail: `https://www.googleapis.com/auth/gmail.readonly`.
  - Outlook: `Mail.Read,User.Read,offline_access`.
- **How:** create *new* managed configs with `options={"type": "use_composio_managed_auth", "credentials": {"scopes": "..."}}`, then switch `BLINKA_COMPOSIO__*_AUTH_CONFIG_ID`. Re-link each account and recreate its trigger.
- **Do not** update the existing config in place. SDK 0.28 `auth_configs.update` drops `scopes`.
- Using your own Google OAuth client in Testing mode expires refresh tokens every 7 days, so avoid it for a demo.

## Edge Cases Identified

- **Two approvals of the same bill at once:** the first wins through the bill CAS. The second gets 409 before any money moves (now guaranteed by the single transaction).
- **Budget exhausted between the R14 check and the reserve:** the transaction rolls back, the verdict becomes HOLD with an R14 blocker, and it is committed again without a reservation.
- **Webhook arrives during a restart:** the row is `received` with `source_payload`, so it is processed once the worker starts. Before this change it would have been lost.
- **The same email redelivered while queued:** the `(provider, external_message_id)` unique constraint drops it, as before.
- **Demo reset while runs are queued:** `purge_owner` deletes the pending rows. A worker that claims a row which disappears mid-claim gets 0 rows, which is harmless. In-flight runs are cancelled through `registry.cancel_owner`.
- **Composio returns EXPIRED for the demo Gmail:** the row is stored as `expired`, the UI shows "Connect Gmail", and re-linking works because `link()` only blocks ACTIVE duplicates.
- **A JWT for a deleted or other user hits the realtime authorizer:** the Lambda still accepts any valid `sub`. That is acceptable because only the demo user can obtain a token now.
