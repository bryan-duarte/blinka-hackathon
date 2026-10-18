# Demo Reset Implementation

## Overview

Resets the demo account to its initial state. It cancels any in-flight work, deletes every row the owner has except mailbox connections, deletes the owner's S3 objects and LangGraph checkpoint threads, then re-seeds.

## Files to Modify/Create

- `backend/core/background.py` `ExecutionRegistry`: track an owner per task and add `cancel_owner`.
- `backend/modules/payments/service.py`:
  - Pass `owner_id` in `start_run` / `start_file_run`.
  - Add `cancel_owner(owner_id) -> int` and `purge_run_threads(run_ids: list[UUID]) -> int`.
- `backend/clients/payments.py`: mirror `cancel_owner` and `purge_run_threads`.
- `backend/modules/files/storage.py`: add `delete_prefix(prefix: str) -> int` to the `StorageBackend` protocol and to `ObjectStorageBackend`.
- `backend/modules/files/service.py` + `backend/clients/files.py`: add `purge_owner_objects(owner_id) -> int`.
- `backend/modules/demo/reset_repository.py` (new): `DemoResetRepository(sessionmaker)` with `collect_owner_refs(owner_id) -> OwnerRefs` and `purge_owner(owner_id) -> dict[str, int]`.
- `backend/modules/demo/service.py`: `reset(owner) -> DemoResetResult`.

## Implementation Guidelines

### Registry (orientative)

```python
class ExecutionRegistry:
    def __init__(self) -> None:
        self._tasks: dict[UUID, asyncio.Task[None]] = {}
        self._owners: dict[UUID, UUID] = {}

    def spawn(self, task_id: UUID, execution: Coroutine[object, object, None], owner_id: UUID | None = None) -> None:
        ...
        if owner_id is not None:
            self._owners[task_id] = owner_id

    def _reap(self, task_id, task):
        self._tasks.pop(task_id, None)
        self._owners.pop(task_id, None)
        ...

    async def cancel_owner(self, owner_id: UUID) -> int:
        owned = [task for task_id, task in self._tasks.items() if self._owners.get(task_id) == owner_id]
        for task in owned:
            task.cancel()
        await asyncio.gather(*owned, return_exceptions=True)
        return len(owned)
```

- Payments runs that are cancelled run their existing `CancelledError` path in `runner.run_execution`, which writes a `cancelled` event. The purge deletes that event afterwards, which is fine.
- Order: demo sequencer registry, then inbox registry, then payments registry. The inbox pipeline spawns payments runs, so cancelling the inbox first stops new runs from being created mid-reset.

### Purge order (`DemoResetRepository.purge_owner`)

Everything runs in one `async with sessionmaker() as session, session.begin()`, using `delete(...)` / `update(...)` scoped by owner, in this order:

1. `agent_run_events` where `run_id IN (select id from agent_runs where owner_id = :o)`
2. `agent_run_files` where `run_id IN (owner runs)` **or** `bill_source_id IN (owner sources)`
3. `payment_decisions` where `bill_id IN (owner bills)`
4. `payments` where `owner_id = :o`
5. `budget_counters` where `owner_id = :o`
6. `update inbox_emails set run_id = NULL, file_id = NULL where owner_id = :o`
7. `update bill_sources set bill_id = NULL where owner_id = :o`
8. `agent_runs` where `owner_id = :o`
9. `bill_sources` where `owner_id = :o`
10. `inbox_emails` where `owner_id = :o`. This keeps `mailbox_connections`.
11. `update bills set duplicate_of_bill_id = NULL where owner_id = :o`, then delete from `bills` where `owner_id = :o`
12. `files` where `owner_id = :o`
13. `blacklist_entries`, then `payee_identifiers` (cascade, but delete explicitly by owner), then `payees`, then `payment_policies`, all where `owner_id = :o`
14. `fx_rates` is global and is not touched. `trusted_forwarders` (07) is also kept, like `mailbox_connections`, so the reviewers' forwarders survive a reset.

Return `{table_name: rowcount}`.

Verify the FK directions against the models before finalizing the order. The nulling steps (6, 7, 11) exist to break the cycles `bill_sources ↔ bills ↔ agent_runs ↔ inbox_emails`. Wrap a failure in `DemoResetFailedError(DemoError)`, which maps to 500 with detail "demo reset failed".

`collect_owner_refs` runs before the purge and returns `OwnerRefs(run_ids: list[UUID], storage_key_count: int)`. The storage keys themselves are not needed, because a prefix delete covers them.

### S3 prefix delete (orientative)

```python
DELETE_BATCH_SIZE = 1000

async def delete_prefix(self, prefix: str) -> int:
    deleted = 0
    async with self._object_client() as client:
        paginator = client.get_paginator("list_objects_v2")
        async for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
            keys = [{"Key": item["Key"]} for item in page.get("Contents", [])]
            for batch_start in range(0, len(keys), DELETE_BATCH_SIZE):
                batch = keys[batch_start : batch_start + DELETE_BATCH_SIZE]
                await client.delete_objects(Bucket=self._bucket, Delete={"Objects": batch, "Quiet": True})
                deleted += len(batch)
    return deleted
```

- Guard it with `if not prefix.endswith("/") or prefix == "/": raise ValueError`, so a bug can never wipe the whole bucket.
- `purge_owner_objects` always passes `f"{owner_id}/"`.

### Checkpoint purge

`purge_run_threads` calls `await checkpointer.adelete_thread(str(run_id))` for each run. That is the LangGraph `AsyncPostgresSaver` API; check the method name against the installed `langgraph-checkpoint-postgres` version. It skips when `checkpointer is None`, logs each failure as a warning, and returns the count it deleted.

### `DemoService.reset` (orientative)

```python
async def reset(self, owner: CurrentUser) -> DemoResetResult:
    if self._lock.locked():
        raise DemoBusyError
    async with self._lock:
        await self._registry.cancel_owner(owner.user_id)
        self._launches_for(owner.user_id).clear()
        await self._inbox.cancel_owner(owner.user_id)
        await self._payments.cancel_owner(owner.user_id)
        refs = await self._reset_repository.collect_owner_refs(owner.user_id)
        deleted_rows = await self._reset_repository.purge_owner(owner.user_id)
        deleted_objects = await self._purge_objects(owner)       # best effort, logs on StorageError
        await self._payments.purge_run_threads(refs.run_ids)     # best effort
        seeded_bills = await self._seeder.seed(owner)
        await self._realtime.publish(owner.user_id, [RealtimeEvent(type=INBOX_ITEM, item_id=None, payload={"status": "reset"}, ...)])
        logger.info("demo_reset_completed", owner_id=owner.user_id, deleted_rows=deleted_rows)
        return DemoResetResult(...)
```

- Check that `RealtimeEvent.item_id` is nullable. If it isn't, use a new event type `demo.reset` in `contracts/realtime.py` and handle it in `useInboxChannel` consumers.
- `launch` must also refuse to start while `self._lock.locked()`.

## Dependencies

- 04 (`DemoSeeder`) and 05 (`DemoService`, launches).
- `PaymentsClient`, `InboxClient`, `FilesClient` and `RealtimeClient`.

## Integration Notes

- 08 exposes the reset as `POST /demo/reset`, which only the demo user can call.
- The frontend (11) shows a confirm dialog, calls the endpoint, then reloads the inbox, budgets and catalog.
