# Sessions

## Overview

Dual-interface session store: **mutable** session state on PG-1 (create/touch/update), **immutable** execution log on PG-3 (append-only — no UPDATE/DELETE methods exist).

## Files to Create

- `backend/modules/sessions/__init__.py` — facade: `SessionsService`, `SessionMissingError`
- `backend/modules/sessions/errors.py` — `SessionMissingError` (→ 404)
- `backend/modules/sessions/models.py` — `SessionRecord(ProductBase)` + `SessionExecution(PaymentsBase)` per 03-design.md.
- `backend/modules/sessions/mutable_repository.py` — `SessionsMutableRepository(sessionmaker_pg1: async_sessionmaker[AsyncSession])`:
  - `create(owner_id, title="") -> UUID`
  - `get(session_id, owner_id) -> SessionRow | None`
  - `list_by_owner(owner_id, limit=50) -> list[SessionRow]`
  - `touch(session_id) -> None` (updates `updated_at`)
- `backend/modules/sessions/immutable_repository.py` — `SessionsImmutableRepository(sessionmaker_pg3: async_sessionmaker[AsyncSession])`:
  - `append(session_id, agent, input_summary, output_summary) -> UUID`
  - `get(execution_id) -> ExecutionRow | None`
  - `list_by_session(session_id, limit=100) -> list[ExecutionRow]`
  - Comment at class top: APPEND-ONLY — INSERT/SELECT only, enforced by not exposing write methods.
- `backend/modules/sessions/service.py`:

```python
class SessionsService:
    def __init__(self, mutable: SessionsMutableRepository, immutable: SessionsImmutableRepository) -> None: ...

    async def ensure_session(self, owner: CurrentUser, session_id: UUID | None) -> UUID
    # None -> create ; else verify ownership (SessionMissingError) + touch

    async def record_execution(self, session_id: UUID, agent: str,
                               input_summary: str, output_summary: str) -> ExecutionRecorded
    async def list_sessions(self, owner: CurrentUser) -> list[SessionSummary]
    async def get_executions(self, session_id: UUID, owner: CurrentUser) -> list[ExecutionRecord]
```

- `backend/clients/sessions.py` — `SessionsClient` mirroring those four methods.
- `contracts/sessions.py` — per 03-design.md.

## Implementation Guidelines

- `input_summary`/`output_summary` are SHORT text (first ~500 chars), not full transcripts — transcripts live in the LangGraph checkpoints.
- Ownership checks always pair `session_id` with `owner_id` in the WHERE clause (no existence leaks).

## Dependencies

02-backend-skeleton, 04-persistence-alembic (sessions + session_executions tables).

## Integration Notes

- Orchestrator: `ensure_session` at chat start; `session_id` doubles as the LangGraph `thread_id` on PG-2.
- Payments runner: on terminal status, `record_execution(session_id?, agent="payments", ...)`. If the run was triggered by chat, the orchestrator passes the originating `session_id` inside `PaymentRunTrigger`; direct REST triggers may omit it (nullable in `PaymentRunTrigger` — add `session_id: UUID | None = None`).
