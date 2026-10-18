# Memory Management UI + Demo Reset

## Overview

People can see every memory the agent uses and delete any of them from `/settings/memories`. A demo reset cancels in-flight extractions and wipes the owner's memories.

## Files to Modify/Create

**Backend**
- `backend/api/routers/memory.py` (new):
  - `GET /memories` returns `list[MemoryView]`.
  - `DELETE /memories/{payee_key}/{memory_id}` returns 204.
  - Both use `CurrentUserDep` and `ClientsDep`.
- `backend/api/routers/__init__.py:24-36`: include the memory router.
- `backend/api/app.py:66-106` `DOMAIN_ERROR_RESPONSES`: map `MemoryNotFoundError` to 404.
- `backend/modules/demo/service.py`:
  - `DemoService.__init__` takes a `memory: "MemoryClient"` keyword.
  - `_cancel_pipelines` (`:210-211`) adds `await self._memory.cancel_owner(owner_id)`.
  - `reset` calls `await self._memory.forget_owner(owner.user_id)` after `purge_run_threads`. Add the count to the log line as `deleted_memories`.
- `backend/container.py` (`:190-200`): pass `memory=memory` to `DemoService(...)`.

**Frontend**
- `frontend/src/lib/types.ts`: `MemoryView` type, mirroring the contract.
- `frontend/src/lib/api.ts`:
  - `memories: () => get<MemoryView[]>("/memories")`
  - `deleteMemory: (payeeKey: string, memoryId: string) => send("DELETE", `/memories/${encodeURIComponent(payeeKey)}/${encodeURIComponent(memoryId)}`)`
  - Use whatever `send`/`del` helper `api.ts:166-171` exposes.
- `frontend/src/app/settings/layout.tsx:8-12`: append `{ href: "/settings/memories", label: "Agent memory" }` to `SETTINGS_TABS`.
- `frontend/src/app/settings/memories/page.tsx` (new): a client page that lists memories grouped by payee, with a delete action.

## Implementation Guidelines

```python
# orientative — api/routers/memory.py
router = APIRouter(prefix="/memories", tags=["memory"])

@router.get("")
async def list_memories(user: CurrentUserDep, clients: ClientsDep) -> list[MemoryView]:
    return await clients.memory.list_for_owner(user.user_id)

@router.delete("/{payee_key}/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(payee_key: str, memory_id: str, user: CurrentUserDep, clients: ClientsDep) -> None:
    await clients.memory.forget(user.user_id, payee_key, memory_id)
```
- Owner isolation comes from the namespace: `forget` only ever touches `("payments_memories", user.user_id, payee_key)`. A foreign `memory_id` returns 404.
- `payee_key` may contain `name:<normalized>`. The normalized name has no `/`, but the frontend still URL-encodes it.

**Page behavior (orientative):**
- Load `api.memories()` on mount, with loading, empty and error states.
- Empty state copy: "No memories yet. Tick “Remember this” when approving or rejecting an invoice."
- Group by `payee`. For each memory, show:
  - `lesson` (primary)
  - `situation`
  - `applies_when` (if present)
  - a badge for `human_action`
  - `note_excerpt` as a quote
  - `updated_at`
  - a link to `/bills?bill=<source_bill_id>` when present
- Delete asks for a confirm step inline (mirror the blacklist page's delete pattern), calls `api.deleteMemory(memory.payee_key, memory.memory_id)`, then removes the row optimistically and reloads on error.
- Include a short header line explaining that memories are advisory and never override payment rules.
- Mirror `app/settings/blacklist/page.tsx` for structure, data loading, errors (`components/settings` helpers) and styles.
- Re-read `frontend/DESIGN.md` fully and follow it strictly. No em-dashes, placeholder names or filler copy in the UI.

## Dependencies

- Module 05 (`list_for_owner`, `forget`, `forget_owner`, `cancel_owner`, `MemoryView`, `MemoryNotFoundError`).

## Integration Notes

- `MemoryView` JSON:
  `{memory_id, payee_key, payee, situation, human_action, lesson, applies_when, source_bill_id, note_excerpt, created_at, updated_at}`
  Datetimes are ISO strings.
- With memory disabled, `GET` returns `[]`, so the page shows the empty state.
- Reset order inside `DemoService.reset`:
  1. `cancel_owner` (via `_cancel_pipelines`)
  2. purge the product DB
  3. purge objects
  4. purge run threads
  5. `forget_owner`
  6. seed

  This order prevents a late background extraction from writing after the wipe.
