# Demo Hardening: Locked Access, Durable Queue, Rich Agent Events, Audited Agent DB

> "We built an agent that refuses to pay twice, then left the front door open so anyone could walk in and watch it count."
> - El Barto

## Overview

**Request**: Verify and persist the demo user's Gmail, Outlook and Kapso sandbox connections for evaluators. Check payment idempotency and race conditions. Raise the concurrency limits and queue the overflow. Send richer agent-execution events to the frontend. Remove the public demo entry so only the demo user can log in. Enable PGAudit on the agent DB with automatic copies to S3.

**Created**: 2026-10-18

## What

| # | Area | Outcome |
|---|------|---------|
| 1 | Access lockdown | The public "Enter the demo" path and self-registration are removed. Only `demo@blinka.dev` can log in, with a password you set in SSM. |
| 2 | Demo integrations | Connection status is reconciled with Composio on read, so expired or revoked accounts show "Reconnect" instead of a false "active". A verification script and an operator checklist confirm the prod demo user has Gmail, Outlook and the WhatsApp sandbox linked. |
| 3 | Settlement atomicity | The bill status check, the money movement and the decision are committed in **one** transaction, so money never moves for a bill whose state changed underneath. |
| 4 | Durable run queue | Agent runs and inbox pipelines go through a Postgres-backed queue. The default is 8 concurrent of each, configurable by env. Overflow waits in the DB and survives restarts. The demo launch cap goes from 5 to 20. |
| 5 | Rich agent events | New live events cover pipeline stages, each policy rule, extraction fields, checker answers, tool output and LLM calls with token counts. |
| 6 | Agent visualization | The inbox panel gets a richer live view, and `/runs/[id]` updates over realtime instead of 3-second polling. |
| 7 | Agent DB split | A new RDS instance, `blinka-prod-agent`, holds only the LangGraph checkpoints. Code is renamed from `payments` DB to `agent` DB. |
| 8 | PGAudit + S3 | Both RDS instances run pgaudit (`ddl,write,role`). Logs flow from CloudWatch through Firehose into an encrypted, versioned S3 bucket. |

**Deferred (by your call):** narrowing the Gmail and Outlook OAuth scopes. The research results are kept in `05-risks.md` so the work can be picked up later.

## Why

- **Evaluators:** they will log in as the demo user and need working email and WhatsApp intake. Today a revoked token still shows "active", and anyone can enter through `/demo/login`.
- **Settlement:** `settle()` moves money *before* checking the bill status (`backend/modules/payments/settlement.py:68-89`).
- **Concurrency:** there is no cap at all. Every run is a bare `asyncio.create_task`, and in-flight webhook work is dropped on restart.
- **Events:** realtime strips almost every useful payload field (`REALTIME_PAYLOAD_KEYS`), so the UI shows a thin view of a rich agent.
- **Agent DB:** the checkpoints share the product RDS instance, and neither instance has audit logging.

## Impact

- **Backend:** auth, demo, inbox, payments (settlement, runner, events, agent), core (config, db, a new work queue), and two new Alembic migrations.
- **Frontend:** the login page, landing CTAs, `lib/api.ts`, `lib/types.ts`, `lib/runEvents.ts`, `AgentActivity`, `runs/[id]`, and `RunTimeline`.
- **Infra:** a new RDS instance and a shared parameter group, an S3 audit bucket, Firehose, CloudWatch subscriptions, SSM param changes, and a reboot of the product RDS (about 1-3 minutes of downtime).

## Flow

```
 webhook / upload / demo launch
            │  (persist + enqueue, return 2xx)
            ▼
 ┌─────────────────────┐   FOR UPDATE SKIP LOCKED   ┌──────────────────────┐
 │ inbox_emails        │ ─────────────────────────▶ │ InboxWorker (≤8)     │──pipeline.stage events──┐
 │ status=received     │                            └─────────┬────────────┘                         │
 └─────────────────────┘                                      │ start_run → agent_runs(pending)      │
 ┌─────────────────────┐   FOR UPDATE SKIP LOCKED   ┌─────────▼────────────┐                         │
 │ agent_runs          │ ─────────────────────────▶ │ RunWorker (≤8)       │──agent.rule / agent.llm ─┤
 │ status=pending      │                            │ deep agent + tools   │  run.step / agent.tool   │
 └─────────────────────┘                            └─────────┬────────────┘                         ▼
                                                              │ settle: ONE tx            AppSync /inbox/{user}
                                         product RDS  ◀───────┘ (CAS bill + pay + decision)      │
                                         agent RDS (checkpoints)                                 ▼
                                         both ── pgaudit ─▶ CloudWatch ─▶ Firehose ─▶ S3   Inbox panel + /runs/[id]
```
