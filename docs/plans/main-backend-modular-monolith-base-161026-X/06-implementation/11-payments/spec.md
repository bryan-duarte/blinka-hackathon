# Payments (Background Agent)

## Overview

Payment DeepAgent with its own PG-3 checkpointer, executed in background (in-process asyncio) with a persisted run/event log in PG-1. Triggered by the orchestrator tool or directly via REST; polled by the UI.

## Files to Create

- `backend/modules/payments/__init__.py` — facade: `PaymentsService`, `RunNotFoundError`
- `backend/modules/payments/errors.py` — `RunNotFoundError` (→ 404), `RunTriggerError`
- `backend/modules/payments/models.py` — `AgentRun(ProductBase)`, `AgentRunEvent(ProductBase)` per 03-design.md.
- `backend/modules/payments/repository.py` — `RunsRepository(sessionmaker_pg1: async_sessionmaker[AsyncSession])`, SQLAlchemy 2.0 `select()`/`update()`:

```python
class RunsRepository:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None: ...
    async def insert_run(self, agent: str, file_id: UUID | None, session_id: UUID | None) -> UUID   # status='pending'
    async def get_run(self, run_id: UUID) -> AgentRun | None
    async def update_status(self, run_id: UUID, status: str, error: str | None = None) -> None
        # ORM update restricted to explicit fields {status, error, updated_at}
    async def insert_event(self, run_id: UUID, step: str, payload: dict) -> None
    async def latest_events(self, run_id: UUID, limit: int = 100) -> list[AgentRunEvent]  # order by id
    async def fail_unfinished(self, reason: str) -> int   # pending|running -> failed, returns count
```

- `backend/modules/payments/agent.py` — `build_payment_agent(llm, checkpointer)`:

```python
def build_payment_agent(llm: LlmGatewayClient, payments_checkpointer) :
    return create_deep_agent(model=llm.model("payments"),
                             system_prompt=get_prompt("payment_agent"),
                             tools=[...minimal base tools...],
                             checkpointer=payments_checkpointer)   # same kwarg resolution as orchestrator
```

Base tools: invoice context lookup wrapper (reads seeded `InvoiceData` from state/input) and a stub `execute_payment` tool that logs an event and returns success — real payment rails are a later phase.

- `backend/modules/payments/runner.py` — background execution:

```python
class ExecutionRegistry:          # in-process supervision
    _tasks: dict[UUID, asyncio.Task]
    def spawn(self, run_id: UUID, coro) -> None   # create_task + add_done_callback(self._reap)
    async def shutdown(self) -> None              # cancel pending, await gathered

async def run_execution(run_id, agent, deps) -> None:
    # insert_event("started") ; update_status("running")
    # try:
    #     invoice = await invoice_ingestor.parse(owner, file_id)   # InvoiceParseError -> fail
    #     insert_event("invoice_parsed", {...})
    #     result = await agent.ainvoke({seeded input + InvoiceData},
    #                config={"configurable": {"thread_id": str(run_id)}})
    #     insert_event("completed", {"summary": ...}) ; update_status("completed")
    #     sessions.record_execution(session_id, "payments", input_summary, output_summary)
    # except Exception as exc:
    #     insert_event("failed", {"error": str(exc)}) ; update_status("failed", error=str(exc))
```

- `backend/modules/payments/service.py` — `PaymentsService(repo, agent_factory, registry, sessions, invoice_ingestor)`:
  - `async start_run(self, trigger: PaymentRunTrigger, owner: CurrentUser) -> PaymentRunAccepted`
    - insert row (`pending`) → `registry.spawn(run_id, run_execution(...))` → return accepted. NEVER awaits the run.
  - `async get_run(self, run_id: UUID, owner: CurrentUser) -> PaymentRunStatus` (run + latest_events; 404 if missing)
  - `async fail_unfinished(self, reason: str) -> None` (lifespan startup sweep)
- `backend/api/routers/payments.py` — `payments_router = APIRouter(prefix="/payments", tags=["payments"])`:
  - `POST /payments/runs` → guardrail check first (serialize trigger context) → 202 `PaymentRunAccepted`
  - `GET /payments/runs/{run_id}` → 200 `PaymentRunStatus` / 404 `run not found`
- `backend/clients/payments.py` — `PaymentsClient.start_run`, `PaymentsClient.get_run`.
- `contracts/payments.py` — add `session_id: UUID | None = None` to `PaymentRunTrigger` (see 09-sessions).

## Implementation Guidelines

- Persist BEFORE spawn (row first, task second) — the 202 + poll contract must never point at a run that doesn't exist.
- `PaymentRunTrigger` needs owner context for invoice parsing: service signature takes `owner` separately (tool path passes the chat user through).
- Run ids are the checkpoint `thread_id` on PG-3 — resumable/inspectable via LangGraph tooling later.
- The registry is intentionally in-memory (documented limitation): after a restart the rows say what happened; the task itself is gone.

## Dependencies

08-llm-gateway-prompts, 07-invoice-ingestor, 09-sessions, 04-persistence-alembic.

## Integration Notes

Called by orchestrator's `initiate_payments` tool (with `session_id`) and by `POST /payments/runs` (guardrail-checked). Polling consumers: frontend UI. `PaymentRunStatus.events` is ordered by `agent_run_events.id`.
