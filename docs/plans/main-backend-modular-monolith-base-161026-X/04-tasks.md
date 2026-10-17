# Implementation Tasks

## Task Breakdown

### Monorepo Restructure
- [x] `git mv apps/web frontend` and `git mv apps/api backend`
- [x] Update `pnpm-workspace.yaml` → `packages: ["frontend", "backend"]`
- [x] Update `turbo.json` (`.next` output path now `frontend/.next/**`)
- [x] Update `frontend/package.json` and `backend/package.json` names (`@blinka/web`, `@blinka/backend`) and scripts
- [x] Replace `backend/app/` stub with the new structure (remove `app/main.py`)

### Backend Skeleton
- [x] `backend/pyproject.toml` (deps above, `[tool.uv] package = false`, ruff + pytest config, `.python-version` = 3.13)
- [x] `backend/core/config.py` — `Settings` (pydantic-settings, `BLINKA_` prefix, nested JWT/LLM/Storage groups)
- [x] `backend/core/logging_config.py` — structlog console/json setup
- [x] `backend/core/db.py` — async pools factory + checkpointer factories
- [x] `backend/contracts/_base.py` — `StrictModel` / `ApiModel`
- [x] All contract files (`auth`, `chat`, `files`, `invoices`, `payments`, `guardrails`, `sessions`, `llm`)
- [x] `backend/container.py` — `Clients` frozen dataclass + `build_clients()`
- [x] `backend/api/app.py` — `create_app()` + lifespan (pools, checkpointers, sweeps, teardown)
- [x] `backend/api/deps.py` — `get_settings`, `get_clients`, `get_current_user`
- [x] `backend/api/routes.py` — router assembly, `/health`
- [x] `backend/.env.example` with every `BLINKA_*` var

### Docker Stack
- [x] `backend/Dockerfile` — uv-based, 2-stage layer caching, non-root, `uvicorn api.app:app`
- [x] `backend/.dockerignore` — `.venv/`, `.env`, `__pycache__`, `.ruff_cache`
- [x] Root `docker-compose.yml` — 3 postgres + minio + backend, healthchecks, volumes, MinIO bucket bootstrap
- [x] Verify `docker compose up` boots the full stack and `/health` responds

### Persistence (SQLAlchemy + Alembic)
- [x] `backend/core/db/` package — `base.py` (`ProductBase`, `PaymentsBase` DeclarativeBase + naming convention), `engine.py` (`create_async_engine` + `async_sessionmaker`), `checkpointers.py`
- [x] ORM models per module: `auth/models.py` (User), `files/models.py` (FileRecord), `invoice_ingestor/models.py` (InvoiceRecord), `payments/models.py` (AgentRun, AgentRunEvent), `sessions/models.py` (SessionRecord, SessionExecution)
- [x] `backend/alembic.ini` + `alembic/env.py` (sections `product`/`payments`, metadata selected by section, all model modules imported)
- [x] Generate initial migrations VIA ALEMBIC CLI AUTOGENERATE (never hand-written): `alembic -n product revision --autogenerate -m "create product tables"` → review → `upgrade head`; same for `payments`
- [x] Startup `AsyncPostgresSaver.setup()` for PG-2/PG-3 in lifespan

### Auth Module
- [x] `modules/auth/repository.py` — `UsersRepository` (insert, get_by_email)
- [x] `modules/auth/service.py` — `AuthService` (register, login, token encode/decode, bcrypt)
- [x] `modules/auth/errors.py` — `EmailTakenError`, `InvalidCredentialsError`
- [x] `clients/auth.py` + facade `__init__.py`
- [x] Routes: `POST /auth/register`, `POST /auth/login`; `get_current_user` dependency

### Files & Storage
- [x] `modules/files/storage.py` — `StorageBackend` Protocol + `S3StorageBackend` (aioboto3, endpoint_url)
- [x] `modules/files/repository.py` — `FilesRepository` (insert, get, list_by_owner, set_parse_status)
- [x] `modules/files/extract.py` — generic text extraction (PDF text via pypdf, passthrough for text/*, unsupported otherwise)
- [x] `modules/files/service.py` — `FilesService` (upload → storage + row; get_context(file_ids) for agents)
- [x] Bucket bootstrap at startup (create if missing)
- [x] `clients/files.py`; route: `POST /files` (multipart, requires auth)
- [x] Add `pypdf` dependency

### Invoice Ingestor
- [x] `modules/invoice_ingestor/service.py` — `InvoiceIngestorService.parse(file_id)` → LLM extraction → `InvoiceData` validation, cache in `invoices` table
- [x] `clients/invoice_ingestor.py`; consumed by payments runner (and later email trigger)

### LLM Gateway & Prompts
- [x] `modules/llm_gateway/service.py` — `LlmGatewayService.model(kind)` returning configured `ChatOpenAI` (OpenRouter base_url)
- [x] `modules/prompts/main_agent.py`, `modules/prompts/payment_agent.py`, `modules/prompts/__init__.py` registry

### Sessions
- [x] `modules/sessions/mutable_repository.py` — `SessionsMutableRepository` (PG-1: create, get, list, touch)
- [x] `modules/sessions/immutable_repository.py` — `SessionsImmutableRepository` (PG-3: append, get, list — NO update/delete)
- [x] `modules/sessions/service.py` — `SessionsService` exposing both interfaces
- [x] `clients/sessions.py`

### Orchestrator (Main Agent)
- [x] `modules/orchestrator/service.py` — builds DeepAgent (`create_deep_agent`, main model from gateway, checkpointer PG-2, `initiate_payments` tool inline)
- [x] `initiate_payments` tool → `PaymentsClient.start_run()`, returns run_id to the conversation
- [x] `chat(request, user)` and `stream_chat(request, user)` (astream_events → ChatStreamEvent)
- [x] File context: `FilesClient.get_context(file_ids)` injected into the agent input
- [x] `clients/orchestrator.py`
- [x] Routes: `POST /chat`, `POST /chat/stream` (SSE) — both guardrail-checked

### Payments (Background Agent)
- [x] `modules/payments/repository.py` — `RunsRepository` (insert run, update status guarded by UPDATABLE set, insert_event, get, latest_events, fail_unfinished)
- [x] `modules/payments/agent.py` — payment DeepAgent builder (payments model, checkpointer PG-3, invoice context seeding via `InvoiceIngestorClient`)
- [x] `modules/payments/runner.py` — registry + `run_execution()` coroutine (status transitions + event writes + terminal state)
- [x] `modules/payments/service.py` — `PaymentsService` (start_run → 202 path; get_run → polling path; startup sweep)
- [x] `clients/payments.py`
- [x] Routes: `POST /payments/runs` (trigger, guardrail-checked), `GET /payments/runs/{run_id}` (polling)

### Stub Modules
- [x] `modules/guardrails/service.py` — pass-through `check()` returning allowed verdict (+ errors.py, client, facade)
- [x] `modules/mcp_gateway/service.py` — skeleton (`list_tools`, `call_tool` contract methods, `McpNotConfiguredError`), client, facade
- [x] `modules/tools/service.py` — skeleton seam only, client, facade

### Wiring & Verification
- [x] Guardrail check wired into `/chat`, `/chat/stream`, `POST /payments/runs` with 422 rejection mapping
- [x] Session records: chat creates/touches session (mutable); payment run completion appends execution record (immutable)
- [x] Startup sweeps wired in lifespan (fail unfinished runs)
- [x] `pnpm dev` runs frontend + backend together; `uv run ruff check .` clean
- [x] Manual smoke: register → login → upload invoice → chat → initiate payments → poll run → see events

### Post-Implementation Quality Gate
- [x] Run a two-subagent quality pass over the recently-applied change:
  - [x] **Bug sweep** — launch a subagent to search the modified code for possible bugs, issues, and inconsistencies (logic errors, edge cases, broken contracts, dead code, regressions). Report concrete findings as `file:line` references.
  - [x] **Polish** — launch a subagent that improves code quality by invoking the `codebase-change` skill and applying the polish DIRECTLY to the changed files: delete unnecessary comments, make the code self-explanatory, give every variable an obvious purpose, maximize readability and maintainability, and remove unnecessary complexity. Resolve any real issues the bug sweep surfaced.

## Task Order

```
restructure ──► skeleton ──► docker ──► persistence ──► auth ──┐
                     │                                          ├─► orchestrator ──► payments ──► wiring
                     ├─► llm_gateway/prompts ───────────────────┤        (chat/SSE)    (runner)
                     ├─► files/storage ──► invoice_ingestor ────┘
                     └─► sessions, stub modules (parallel anytime after skeleton)
```
