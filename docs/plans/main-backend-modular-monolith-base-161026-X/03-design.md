# Technical Design

## Architecture Decisions

- **Modular monolith, reference pattern**: top-level-by-role layering (`api/ contracts/ clients/ core/ modules/`) directly inside `backend/`. No `src/`, no brand package. Module implementations are imported at runtime only by `container.py`; clients import services behind `TYPE_CHECKING` only.
- **One process, one port (8000)**: API, agents, and background runner in a single FastAPI process. Microservice-readiness comes from the client seam, not infra.
- **Module contract rule**: a module's public surface is its `__init__.py` facade. Cross-module data crosses ONLY as pydantic contracts. Clients are the only seam between modules.
- **Contract strictness tiers**: `StrictModel` (internal: `extra="forbid", frozen=True, strict=True`) vs `ApiModel` (HTTP edge: `extra="forbid", frozen=True`, coercion allowed) — verbatim from the reference repo's `contracts/_base.py`.
- **3 DBs**: PG-1 product (users, files, invoices, agent_runs, agent_run_events, sessions-mutable), PG-2 main-agent LangGraph checkpoints ONLY, PG-3 payment-agent checkpoints + sessions-immutable log.
- **ORM-first persistence**: SQLAlchemy 2.0 declarative models from day one. Every table is an ORM model; repositories query via `AsyncSession` (SQLAlchemy 2.0 style: `select()`/`insert()`), never raw SQL strings. Two `DeclarativeBase` classes — `ProductBase` (PG-1) and `PaymentsBase` (PG-3) — so each DB has its own metadata.
- **Migrations ALWAYS via Alembic autogenerate**: model change → `alembic -n <section> revision --autogenerate -m "..."` → review generated file → `alembic -n <section> upgrade head`. Migration files are NEVER written by hand. Sections `product` and `payments`, each with its own `version_table`.
- **Checkpoints via LangGraph, not Alembic**: `AsyncPostgresSaver.from_conn_string(dsn)` + `await checkpointer.setup()` at startup for PG-2/PG-3. LangGraph checkpoint tables are NOT ORM models — only `setup()` creates them.
- **Background runs**: in-process `asyncio.create_task` + registry + persisted run/event log; startup sweep marks orphaned `running` → `failed`. Restart loses in-flight tasks, never the record.
- **Streaming**: SSE (`text/event-stream`), events are `ChatStreamEvent` contracts serialized as JSON data frames.
- **Files**: provider-agnostic `StorageBackend` protocol; S3-compatible impl via aioboto3 (MinIO now, AWS S3 later — only endpoint/creds change).
- **LLM**: OpenRouter via `langchain_openai.ChatOpenAI(base_url=...)` — swappable later inside `llm_gateway` only. The gateway is the ONLY place models are constructed.
- **Guardrails**: pass-through stub but real call path (both chat and direct payment trigger call `check()`); enforcement fills in later behind the same contract.
- **Auth**: JWT HS256 access token, bcrypt hashes, `users` in PG-1. Everything except `/health` and `/auth/*` requires a valid bearer token.

## Patterns & Conventions

Mirror the reference repo (`hackathon-anonymous-oct`) exactly, adjusted for no-brand-package:

- **Facade**: `modules/<name>/__init__.py` re-exports service, errors, public helpers; defines `__all__`.
- **Service**: `modules/<name>/service.py`, class `<Name>Service`, async public methods, `_private` helpers, module-level `UPPER_SNAKE` constants.
- **Client**: `clients/<name>.py`, class `<Name>Client`, holds `self._service`, one async method per contract op (same name as service), takes the service in the constructor, accepts/returns contracts only.
- **Composition root**: `container.py` — frozen `@dataclass class Clients`, async `build_clients(settings, ...) -> Clients`; the ONLY place services are instantiated. Stored on `app.state`.
- **App factory**: `api/app.py` — `create_app()` + `lifespan` (pools, checkpointers, container, startup sweeps, teardown).
- **Routes**: ALL HTTP in `api/` — `api/app.py` (factory + lifespan), `api/deps.py` (GLOBAL deps only: `get_settings`, `get_clients`, `get_current_user`), `api/routers/` package with one file per HTTP domain (`auth.py`, `chat.py`, `files.py`, `payments.py`). Each router file owns its endpoints AND its router-specific dependencies, declared inline (`ClientsDep = Annotated[Clients, Depends(get_clients)]` reused everywhere). `api/routers/__init__.py` assembles the `api_router`. **`modules/` must not import FastAPI.**
- **Errors**: module-specific exception types in `modules/<name>/errors.py`; mapped to HTTP in `create_app` via exception handlers.
- **Models**: one `models.py` per module that owns tables (`modules/auth/models.py`, `modules/files/models.py`, ...). SQLAlchemy 2.0 `Mapped[...]`/`mapped_column` style; `snake_case` tables, uuid PKs via `default=uuid4` (Python-side), `created_at` via `server_default=func.now()`.
- **Repos**: `<Entity>Repository` classes receiving an injected `async_sessionmaker[AsyncSession]`; all queries via SQLAlchemy 2.0 constructs. Update paths restricted to explicit column allowlists.
- **Naming**: contracts named `{Noun}{Op}Request` in / `{Noun}{Outcome}` out; `StrEnum` members UPPER_SNAKE, values lowercase.
- **HTTP statuses**: 202 for accepted background work, 422 for guardrail rejections, 404 lowercase short messages, 401 missing/invalid token, 503 dependency down.

## Dependencies

`backend/pyproject.toml` (`requires-python = ">=3.13"`, `[tool.uv] package = false`):

```
fastapi>=0.115            uvicorn[standard]>=0.34
pydantic>=2               pydantic-settings>=2
sqlalchemy[asyncio]>=2.0  # ORM models + async sessions (psycopg3 driver)
psycopg[binary,pool]>=3.2
alembic>=1.14
deepagents>=0.7
langgraph>=1.0            langgraph-checkpoint-postgres>=2
langchain-openai>=1.0     # ChatOpenAI → OpenRouter base_url
aioboto3>=13
pyjwt>=2.10               bcrypt>=4
structlog>=25
python-multipart>=0.0.20  # file upload

dev: ruff>=0.11, pytest>=9, pytest-asyncio>=1.4, httpx>=0.28
```

Build backend: hatchling (metadata only; project is not installed — `[tool.uv] package = false`).

## Integration Points

- Entry: `uvicorn api.app:app` run from `backend/` (imports are `from modules.x import ...`, `from contracts.x import ...` — `backend/` is cwd/sys.path root).
- `api/app.py:lifespan` → `core/db.py` pools + checkpointers → `container.build_clients` → `app.state.clients`.
- `api/deps.py` → `get_current_user` (JWT) → `get_clients` → route handlers use `ClientsDep`.
- `orchestrator` → `clients.payments.start_run()` (fire-and-forget background run) → returns `PaymentRunAccepted`.
- `payments` runner → `clients.invoice_ingestor.parse()` for invoice context seeding; writes `agent_runs`/`agent_run_events` via its repository (PG-1); checkpoints to PG-3.
- `files` → `StorageBackend` (MinIO); `invoice_ingestor` reads file bytes via `FilesClient`.
- `sessions` mutable repo → PG-1 pool; immutable repo → PG-3 pool; both behind one `SessionsClient`.
- Turbo: root `pnpm dev` runs `frontend` (Next) + `backend` (uvicorn) concurrently.

## Data Structures

### SQLAlchemy models (all under `modules/<owner>/models.py`)

PG-1 `blinka_product` → `ProductBase` metadata → Alembic section `product`:

```python
# modules/auth/models.py
class User(ProductBase):
    __tablename__ = "users"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(unique=True, index=True)   # stored lowercase
    password_hash: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

# modules/files/models.py
class FileRecord(ProductBase):        # table "files"
    id, owner_id (FK users.id, index), filename, mime, size_bytes,
    storage_key, parse_status (default "pending"), created_at

class InvoiceRecord(ProductBase):     # table "invoices" — file_id UNIQUE FK, data (JSONB)

# modules/payments/models.py
class AgentRun(ProductBase):          # table "agent_runs"
    id, agent, status (default "pending"), file_id (FK, nullable),
    error (nullable), created_at, updated_at

class AgentRunEvent(ProductBase):     # table "agent_run_events"
    id: Mapped[int] = mapped_column(Identity(), primary_key=True)   # ordering matters for polling
    run_id (FK agent_runs.id, index), step, payload (JSONB, default {}), created_at

# modules/sessions/models.py
class SessionRecord(ProductBase):     # table "sessions"
    id, owner_id (FK users.id), title (default ""), created_at, updated_at
```

PG-3 `blinka_payments` → `PaymentsBase` metadata → Alembic section `payments`:

```python
# modules/sessions/models.py (same file, PaymentsBase)
class SessionExecution(PaymentsBase):   # table "session_executions" — APPEND-ONLY
    id, session_id, agent, input_summary, output_summary,
    occurred_at (server_default=func.now())
```

PG-2 `blinka_agent`: no ORM models — only LangGraph checkpoint tables (created by `setup()`).

Indices: `files.owner_id`, `agent_runs.status`, `agent_run_events.run_id` (via `index=True`).

### Key contracts (`contracts/`)

```python
# contracts/_base.py — identical to reference repo (StrictModel / ApiModel)

# contracts/auth.py
RegisterRequest(email: EmailStr, password: str = Field(min_length=8))
LoginRequest(email: EmailStr, password: str)
TokenResponse(access_token: str, token_type: Literal["bearer"] = "bearer")

# contracts/chat.py
ChatRequest(message: str = Field(min_length=1), session_id: UUID | None = None,
            file_ids: list[UUID] = [])
ChatResponse(reply: str, session_id: UUID, payments_run_id: UUID | None = None)
ChatStreamEvent(type: Literal["token","tool_started","payments_scheduled","done","error"],
                data: dict = {})

# contracts/files.py
FileUploadResult(file_id: UUID, filename: str, mime: str, size_bytes: int,
                 parse_status: FileParseStatus)
FileParseStatus(StrEnum): PENDING PARSED FAILED UNSUPPORTED

# contracts/invoices.py
InvoiceLineItem(description: str, quantity: float, unit_price: float, total: float)
InvoiceData(vendor: str, number: str, issue_date: str | None, due_date: str | None,
            currency: str, total_amount: float, line_items: list[InvoiceLineItem] = [])
InvoiceParseResult(file_id: UUID, invoice: InvoiceData | None, error: str | None = None)

# contracts/payments.py
PaymentRunTrigger(file_id: UUID)                     # direct REST trigger
PaymentRunAccepted(run_id: UUID, status: RunStatus)
PaymentRunStatus(run_id: UUID, status: RunStatus, error: str | None,
                 events: list[PaymentRunEvent])
PaymentRunEvent(step: str, payload: dict, created_at: datetime)
RunStatus(StrEnum): PENDING RUNNING COMPLETED FAILED

# contracts/guardrails.py
GuardrailCheckRequest(context: str)
GuardrailViolation(code: str, message: str)
GuardrailVerdict(allowed: bool, violations: list[GuardrailViolation] = [])

# contracts/sessions.py
SessionCreated(session_id: UUID)
SessionSummary(session_id: UUID, title: str, updated_at: datetime)
ExecutionRecorded(execution_id: UUID)
ExecutionRecord(execution_id: UUID, session_id: UUID, agent: str,
                input_summary: str, output_summary: str, occurred_at: datetime)

# contracts/llm.py
ModelSpec(kind: Literal["main","payments"])          # gateway returns a configured chat model
```

### Settings (`core/config.py`, env_prefix `BLINKA_`, `env_file=".env"`)

```python
class Settings(BaseSettings):
    product_database_url: str        # BLINKA_PRODUCT_DATABASE_URL
    agent_database_url: str          # BLINKA_AGENT_DATABASE_URL (PG-2 checkpoints)
    payments_database_url: str       # BLINKA_PAYMENTS_DATABASE_URL (PG-3)
    jwt_secret: SecretStr            # BLINKA_JWT__SECRET (nested: BLINKA_JWT__*)
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60
    llm: LlmSettings                 # base_url (OpenRouter), api_key alias OPENROUTER_API_KEY,
                                     # main_model, payments_model
    storage: StorageSettings         # endpoint_url, bucket=blinka-files, access_key_id, secret_access_key
    log_format: Literal["console","json"] = "console"
```

### SSE frame

```
event: message
data: {"type":"token","data":{"text":"..."}}

event: message
data: {"type":"payments_scheduled","data":{"run_id":"..."}}

event: message
data: {"type":"done","data":{"session_id":"..."}}
```
