# User Preferences & Decisions

## 👤 Configuration Preferences

- **Context Level**: Superficial (`--low` — T1/T2 exploration: local repo map + reference repo analysis)
- **Participation Level**: Control pleno (`--high` — 20 questions asked, all decisions user-driven)
- **Detail Level**: Neutral (`--mid` — orientative snippets; implementer decides final code)

## 💬 Q&A and Rationale

### 🏗️ Skeleton & Tooling

**Q:** Where should the backend modular monolith live?
**A:** Restructure the monorepo: the two apps move to the root as `frontend/` and `backend/`. The backend app is `backend/`.
**Decision:** Drop the `apps/` nesting. `git mv apps/web frontend`, `git mv apps/api backend`; update `pnpm-workspace.yaml`, `turbo.json`, root scripts.
**Rejected:** Keep `apps/api` — user explicitly wants root-level `frontend/` + `backend/`.

**Q:** Python package layout?
**A:** "Just use backend/ and inside this all the folder structure of this backend."
**Decision:** No `src/` and no brand package. `backend/` IS the import root: top-level packages `api/`, `clients/`, `contracts/`, `core/`, `modules/` directly under `backend/`. Run uvicorn/pytest from `backend/`. pyproject uses `[tool.uv] package = false` (virtual project; deps only).
**Rejected:** `src/blinka` — adds a package layer the user explicitly declined.

**Q:** Python version?
**A:** 3.13 (already pinned in `.python-version`).
**Decision:** Keep `3.13`; Docker image `python:3.13-slim`.

**Q:** Lint/type tooling?
**A:** Ruff only.
**Decision:** `ruff` (E,F,I,UP,B,ASYNC), line-length 100. No mypy/pyright.

### 🗄️ Data Layer

**Q:** Purposes of the 3 PostgreSQL instances?
**A:** 3 DBs as described.
**Decision:** PG-1 `blinka_product` (:5432) — product data. PG-2 `blinka_agent` (:5433) — main agent LangGraph checkpoints only. PG-3 `blinka_payments` (:5434) — payment agent checkpoints + SessionService immutable log.

**Q:** Which DB does SessionService's immutable interface target?
**A:** PG-3 (payments DB).
**Decision:** Mutable interface → PG-1; immutable (append-only) execution log → PG-3.

**Q:** Schema creation strategy?
**A:** Alembic.
**Decision:** Alembic with named sections (`product`, `payments`) sharing one `alembic/` dir. LangGraph checkpoint tables are NOT alembic-managed — `AsyncPostgresSaver.setup()` creates them at startup.

**Q:** DB driver?
**Decision (agent, no question needed — forced by LangGraph):** `psycopg3` everywhere: SQLAlchemy async engine (psycopg driver) for app data, sync for Alembic env, and it's what `langgraph-checkpoint-postgres` uses internally. (Access style later upgraded to SQLAlchemy ORM — see Persistence revision below.)

### 🤖 Agents & Background Execution

**Q:** Where does the payment agent live?
**A:** Own module.
**Decision:** `modules/payments/` owns the payment DeepAgent, its runner, its checkpoint wiring. Orchestrator's `initiate_payments` tool only calls `PaymentsClient`.

**Q:** Background execution mechanism?
**A:** In-process asyncio.
**Decision:** `asyncio.create_task` supervised by an in-process registry + `agent_runs`/`agent_run_events` tables in PG-1. Startup sweep fails unfinished runs ("interrupted by restart"). No Redis/broker.

**Q:** Streaming transport?
**A:** SSE.
**Decision:** `text/event-stream` via `StreamingResponse` + `astream_events`.

**Q:** Monitoring persistence granularity?
**A:** Runs + event log.
**Decision:** `agent_runs` (id, agent, status, invoice file_id, error) + append-only `agent_run_events` (run_id, step, payload, ts). Polling returns run + events.

### 🌐 API Surface

**Q:** How do invoice files enter the system?
**A:** Generic upload — invoices come in many formats; need a general upload that becomes agent context.
**Decision:** `modules/files/` + `POST /files` (multipart, any format) → S3-compatible storage + metadata in PG-1. Chat and payment runs reference `file_id`s. `modules/invoice_ingestor/` specializes in parsing invoice files (LLM extraction → validated `InvoiceData`).

**Q:** Do direct payment-agent REST triggers pass guardrails?
**A:** Yes — chat + direct trigger.
**Decision:** Both entry points call `GuardrailsClient.check()` before execution (stub returns allowed for now, but the call is wired).

**Q:** Email trigger scope?
**A:** Stub, no email yet.
**Decision:** No email listener in this phase; `invoice_ingestor` is the future hook point.

**Q:** Auth?
**A:** JWT users.
**Decision:** `modules/auth/` with `users` table (PG-1), `POST /auth/register`, `POST /auth/login`, HS256 access token (pyjwt), bcrypt hashing, `get_current_user` dependency on all protected routes. No refresh flow.

### 🔌 Gateways & Config

**Q:** File storage?
**A:** MinIO/S3 container; later real S3 — implementation must be provider-agnostic.
**Decision:** `StorageBackend` Protocol in `modules/files/` + `S3StorageBackend` (aioboto3, `endpoint_url`-driven → works with MinIO and AWS S3 alike). Bucket `blinka-files`.

**Q:** File → agent context?
**A:** Invoices LLM + generic extraction.
**Decision:** Invoice files → LLM extraction to `InvoiceData` (via `invoice_ingestor`); other files → basic text extraction (PDF text); binary/images attach as references/multimodal attachments.

**Q:** JWT scope? — see Auth above (access token only).

**Q:** LLM provider?
**A:** OpenRouter temporarily; will change later.
**Decision:** `modules/llm_gateway/` builds `ChatOpenAI` instances pointed at OpenRouter (`base_url=https://openrouter.ai/api/v1`, `OPENROUTER_API_KEY`). Model names configurable per agent. Swap later = touch only the gateway.

**Q:** MCP Gateway scope?
**A:** Skeleton only.
**Decision:** `modules/mcp_gateway/` with client+service+contracts surface (`list_tools`, `call_tool` raising `NotImplementedError`-style); no real MCP server wired.

**Q:** ToolService scope?
**A:** Skeleton only.
**Decision:** `modules/tools/` has the client seam; the `initiate_payments` tool lives inline in `modules/orchestrator/` for now and moves into `tools/` later.

**Q:** Guardrails depth?
**A:** Pass-through stub.
**Decision:** `modules/guardrails/` returns `allowed=True` but the full call path (contracts, client, API error mapping) is real.

**Q:** docker-compose contents?
**A:** Full stack.
**Decision:** 3 postgres + minio + backend, healthchecks, named volumes, ports 5432/5433/5434/9000/9001/8000.

### 📁 Folder Structure (post-plan review)

**Q:** Which backend folder structure — the plan named layers but showed no concrete tree, and the API layer needed a router/DI story?
**A:** Option A — Layer-first (reference repo style).
**Decision:** ALL HTTP lives in `backend/api/`: `app.py` (factory+lifespan), `deps.py` (GLOBAL deps only: settings, clients, current_user), `routers/` (one file per HTTP domain — auth.py, chat.py, files.py, payments.py — each owning its routes AND its router-specific deps, declared inline). `modules/` contains ZERO FastAPI imports (framework-agnostic business logic). Clients + contracts seams unchanged.
**Rejected:** B vertical slices (router/ inside each module — higher cohesion but lets HTTP concerns leak into modules); C flat feature packages (no clients/contracts seams — violates the client-per-layer requirement).

### 🗃️ Persistence revision (post-plan review)

**Q:** (User directive) Use SQLAlchemy models from the beginning; migrations only ever via the Alembic CLI.
**A:** Confirmed.
**Decision:** This OVERRIDES the earlier "raw SQL repositories" agent default. SQLAlchemy 2.0 declarative models per module (`models.py`), repos query via `AsyncSession`; migrations are ALWAYS `alembic -n <section> revision --autogenerate` → review → `upgrade head`. Hand-written migration files are forbidden. Two DeclarativeBases (`ProductBase` PG-1, `PaymentsBase` PG-3) keep autogenerate correct per database.
**Rejected:** Raw SQL + hand-authored migrations (previous default — replaced).

### ⚙️ Agent decisions (no question asked, low-risk defaults)

- **Settings prefix**: `BLINKA_` (pydantic-settings, `env_file=backend/.env`).
- **DB names/creds (local)**: `blinka_product` / `blinka_agent` / `blinka_payments`, user `blinka`, password `blinka`.
- **MinIO creds (local)**: `minioadmin`/`minioadmin`, bucket auto-created at startup.
- **JWT defaults**: HS256, 60-min expiry, secret from `BLINKA_JWT__SECRET`.
- **API port**: 8000 (already the repo convention).
- **JWT lib**: `pyjwt` (not python-jose), hashing: `bcrypt` directly (not stale passlib).
- **S3 client**: `aioboto3` (async, endpoint_url-agnostic).
