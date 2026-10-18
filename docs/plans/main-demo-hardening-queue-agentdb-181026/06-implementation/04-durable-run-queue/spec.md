# Durable Run Queue Implementation

## Overview

Replace the unbounded `ExecutionRegistry.spawn` dispatch for agent runs and inbox pipelines with a Postgres-backed queue:
- Rows wait in their initial status: `agent_runs.status='pending'`, `inbox_emails.status='received'`.
- A `QueueWorker` claims them with `FOR UPDATE SKIP LOCKED`, up to N running at once.
- Overflow waits in the DB and survives restarts and deploys.

This module also raises the DB pool sizes, moves the checkpointer to a connection pool, and lifts the demo launch cap to 20.

## Files to Modify/Create

- `backend/core/config.py`: add `WorkerSettings` (env prefix `BLINKA_WORKERS__`) and `Settings.workers`; add `DemoSettings.max_running_launches: int = 20` (shapes in `03-design.md`).
- `backend/core/work_queue.py` (new): exports `QueueWorker`.
- `backend/core/db/engine.py`: `create_engine_and_sessionmaker(dsn, pool_size, max_overflow)` passes these through to `create_async_engine(..., pool_size=, max_overflow=, pool_pre_ping=True)`; `build_pools(...)` takes them.
- `backend/core/db/checkpointers.py`: switch from `AsyncPostgresSaver.from_conn_string` to an `AsyncConnectionPool` (`psycopg_pool`) with `max_size=checkpointer_pool_size`, `kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row}`, and `AsyncPostgresSaver(pool)`. Open and close the pool in `open()` / `close()`.
- `backend/alembic/versions/product/<rev>_add_inbox_queue_columns.py` (new; generate with `alembic -n product revision`):
  - `inbox_emails.source_payload` JSONB NULL
  - `inbox_emails.pipeline_stages` JSONB NOT NULL server_default `'[]'::jsonb` (used by module 05)
  - index `ix_inbox_emails_status_created (status, created_at)`
  - index `ix_agent_runs_status_created (status, created_at)`
- `backend/modules/inbox/models.py`: add the two columns and the index to `InboxEmailRow`.
- `backend/modules/payments/models.py`: add the index on `AgentRunRow`.
- `backend/modules/payments/repository.py`:
  - add `claim_pending_runs(limit) -> list[QueuedRun]`;
  - `fail_unfinished` (lines 162-172) now fails only `RunStatus.RUNNING`.
- `backend/modules/inbox/repository.py`:
  - `insert_email(...)` (lines 144-167) also takes `source_payload: dict` and writes it in the same insert;
  - add `claim_received_emails(limit) -> list[QueuedEmail]`;
  - inbox `fail_unfinished` now fails only `PROCESSING` / `ANALYZING`, plus `RECEIVED` rows whose `source_payload IS NULL` (legacy).
- `backend/modules/inbox/pipeline.py`: add `dump_source(source: InboxSource) -> dict` and `load_source(payload: dict) -> InboxSource` (discriminator `kind`: `mail_trigger` | `whatsapp_document` | `fetched_email`, using `model_dump(mode="json")` / `model_validate`).
- `backend/modules/inbox/service.py`:
  - `_receive` passes `dump_source(source)` to `insert_email`;
  - `_accept` (lines 302-310) keeps the `RECEIVED` notifier call, replaces `self._registry.spawn(...)` with `self._worker.notify()`, and emits the `pipeline.stage` `queued` event (module 05);
  - add `async def process_claimed(self, email: QueuedEmail) -> None`, which loads the owner via `auth.get_user` and `await`s `process_email(email.email_id, owner, load_source(email.source_payload), deps)`.
- `backend/modules/payments/service.py`:
  - `start_run` (lines 103-108) replaces `self._registry.spawn(...)` with `self._worker.notify()`;
  - add `async def execute_claimed(self, run: QueuedRun) -> None`, which loads the owner and `await`s `run_execution(run.run_id, owner, run.bill_source_id, self._dependencies)`.
- `backend/container.py`:
  - build two `QueueWorker`s, `agent_run_worker` and `inbox_worker`;
  - inject them into `PaymentsService` and `InboxService` (constructor arg `worker`);
  - expose them on `Clients` (or on the services) so `lifespan` can start and stop them.
- `backend/api/app.py` `lifespan` (lines 109-141):
  - after the recovery calls (lines 118-120), `await clients.workers.start()`;
  - in `finally`, `await clients.workers.stop()` **before** the registries shut down.
- `backend/modules/demo/service.py`: replace the constant `MAX_RUNNING_LAUNCHES_PER_OWNER = 5` (lines 56-57) with `self._settings.max_running_launches`.
- `backend/modules/demo/sequencer.py:31`: change `STEP_TIMEOUT_SECONDS` from 150 to 300.
- `backend/.env.example`: add the `BLINKA_WORKERS__*` keys with their defaults.

## Implementation Guidelines

```python
# backend/core/work_queue.py (orientative)
ClaimBatch = Callable[[int], Awaitable[list[T]]]
HandleItem = Callable[[T], Awaitable[None]]

class QueueWorker(Generic[T]):
    def __init__(self, name: str, claim: ClaimBatch[T], handle: HandleItem[T],
                 item_id: Callable[[T], UUID], item_owner: Callable[[T], UUID],
                 registry: ExecutionRegistry, concurrency: int, poll_interval_seconds: float) -> None:
        self._slots = asyncio.Semaphore(concurrency)
        self._wake = asyncio.Event()
        self._loop_task: asyncio.Task[None] | None = None
        ...

    def notify(self) -> None:
        self._wake.set()

    async def start(self) -> None:
        self._loop_task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        if self._loop_task: self._loop_task.cancel(); await asyncio.gather(self._loop_task, return_exceptions=True)

    async def _run_loop(self) -> None:
        while True:
            free_slots = self._free_slots()
            claimed = await self._claim(free_slots) if free_slots else []
            for item in claimed:
                await self._slots.acquire()
                self._registry.spawn(self._item_id(item), self._run_one(item), owner_id=self._item_owner(item))
            if not claimed:
                await self._wait_for_work()            # wake on notify() or poll_interval timeout

    async def _run_one(self, item: T) -> None:
        try:
            await self._handle(item)
        finally:
            self._slots.release()
            self._wake.set()                           # a slot freed: try claiming again
```

- **Free slots:** track an `_in_flight` counter, or use `self._slots._value`. Prefer an explicit counter.
- **Claim errors:** wrap the claim in try/except, `logger.exception("queue_claim_failed", queue=name)`, back off for `poll_interval_seconds`, and keep the loop alive.
- **Logging:** log `queue_claimed` with the count and `queue_backlog_waiting` when claimed equals free slots (saturated).
- **Cancellation:** `registry.cancel_owner` (demo reset) still cancels in-flight items, and `_run_one`'s `finally` releases the slot.

```python
# payments/repository.py claim (orientative)
async def claim_pending_runs(self, limit: int) -> list[QueuedRun]:
    pending_ids = (
        select(AgentRunRow.id)
        .where(AgentRunRow.status == RunStatus.PENDING)
        .order_by(AgentRunRow.created_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
        .scalar_subquery()
    )
    statement = (
        update(AgentRunRow)
        .where(AgentRunRow.id.in_(pending_ids))
        .values(status=RunStatus.RUNNING, updated_at=func.now())
        .returning(AgentRunRow.id, AgentRunRow.owner_id, AgentRunRow.bill_source_id)
    )
    async with self._sessionmaker() as session, session.begin():
        rows = (await session.execute(statement)).all()
    return [QueuedRun(run_id=r.id, owner_id=r.owner_id, bill_source_id=r.bill_source_id) for r in rows]
```

- The inbox claim is the same shape, over `InboxEmailRow` with `status == RECEIVED AND source_payload IS NOT NULL`. It sets `PROCESSING` and returns `id, owner_id, source_payload`.
- **Run status.** `run_execution` already sets RUNNING (`runner.py`). Make that call idempotent, or drop it, because the claim now sets RUNNING. Keep the `started` event.
- **Data models.** `QueuedRun` and `QueuedEmail` are frozen dataclasses (or `StrictModel`s) defined in each module's repository or contracts file.
- **Ordering in `start_run`.** `insert_run` commits before `notify()`, so the worker always sees the row.
- **Demo.** `inbox.inject` goes through `_accept`, so demo scenarios are queued too.

```python
# checkpointers.py (orientative)
class Checkpointers:
    def __init__(self, agent_dsn: str, pool_size: int) -> None:
        self._pool = AsyncConnectionPool(conninfo=agent_dsn, max_size=pool_size, open=False,
                                         kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row})
        self.agent: BaseCheckpointSaver | None = None

    async def open(self) -> None:
        await self._pool.open()
        saver = AsyncPostgresSaver(self._pool)
        await saver.setup()
        self.agent = saver

    async def close(self) -> None:
        await self._pool.close()
```

Note that the `payments` → `agent` attribute rename comes from module 07. Apply both renames together.

## Dependencies

- Module 07: `agent_database_url` and `Checkpointers` naming.
- Module 03: implement it first so queued runs settle atomically.
- Module 05 uses `inbox_emails.pipeline_stages`, created by this module's migration.
- `psycopg_pool`, already present through `langgraph-checkpoint-postgres`. If it is missing, add it with `uv add psycopg-pool`.

## Integration Notes

- **HTTP contracts unchanged:**
  - `POST /payments/runs` still returns 202 `{run_id, status: "pending", duplicate}`.
  - Webhooks still return 202/200 immediately.
- **The UI already handles waiting:** `pending` runs and `received` items are existing statuses it renders.
- **Restart semantics:**
  - `running` runs and `processing`/`analyzing` emails are failed or recovered (current behaviour).
  - `pending` and `received` rows are processed once the workers start.
- **Single instance:** keep `desired_count=1` (see `05-risks.md`).
