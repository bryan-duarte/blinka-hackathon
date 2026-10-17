# Backend Skeleton

## Overview

Core scaffolding of the modular monolith inside `backend/`: pyproject, config, logging, DB factories, contracts, composition root, app factory, deps, routes, `.env.example`.

## Files to Create

- `backend/pyproject.toml` — deps per 03-design.md; `[tool.uv] package = false`; ruff (`line-length=100`, `target-version="py313"`, select E,F,I,UP,B,ASYNC, `isort.known-first-party = ["api","clients","contracts","core","modules"]`); pytest (`testpaths=["tests"]`, `pythonpath=["."]`, `asyncio_mode="auto"`); build-backend hatchling.
- `backend/core/__init__.py`, `backend/core/config.py`:

```python
class JwtSettings(BaseSettings):  # nested via BLINKA_JWT__*
    secret: SecretStr
    algorithm: str = "HS256"
    expire_minutes: int = 60

class LlmSettings(BaseSettings):
    base_url: str = "https://openrouter.ai/api/v1"
    api_key: SecretStr = Field(alias="OPENROUTER_API_KEY", default=SecretStr(""))
    main_model: str = "anthropic/claude-sonnet-4.5"
    payments_model: str = "anthropic/claude-haiku-4.5"

class StorageSettings(BaseSettings):
    endpoint_url: str = "http://localhost:9000"
    bucket: str = "blinka-files"
    access_key_id: str = "minioadmin"
    secret_access_key: SecretStr = SecretStr("minioadmin")

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BLINKA_", env_file=".env", extra="ignore")
    product_database_url: str
    agent_database_url: str
    payments_database_url: str
    jwt: JwtSettings = Field(default_factory=JwtSettings)
    llm: LlmSettings = Field(default_factory=LlmSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    guardrails_enforce: bool = False   # stub kill-switch for the 422 path
    log_format: Literal["console", "json"] = "console"
```

Nested group gotcha: nested BaseSettings with `env_prefix` do NOT inherit the parent prefix — fields read `JWT_SECRET`/`LLM_BASE_URL` (no `BLINKA_`). Either set `env_prefix="BLINKA_"` on each nested class or use aliases; pick one convention, document it in `.env.example`.

- `backend/core/logging_config.py` — `configure_logging(fmt)` + `get_logger()` (structlog).
- `backend/core/db/` package (see 04-persistence-alembic for `base.py`/`engine.py`):
  - `core/db/base.py` — `ProductBase` / `PaymentsBase` (DeclarativeBase, naming convention)
  - `core/db/engine.py` — `create_engine_and_sessionmaker(dsn) -> (AsyncEngine, async_sessionmaker[AsyncSession])`
  - `core/db/checkpointers.py` — `agent_checkpointer(dsn) -> AsyncPostgresSaver` (langgraph `from_conn_string`; opened as async ctx managers in lifespan, `.setup()` awaited once)

- `backend/contracts/__init__.py`, `_base.py` (copy verbatim from reference `contracts/_base.py`: `StrictModel`, `ApiModel`) and one file per module per 03-design.md: `auth.py`, `chat.py`, `files.py`, `invoices.py`, `payments.py`, `guardrails.py`, `sessions.py`, `llm.py`.
- `backend/container.py`:

```python
@dataclass(frozen=True)
class Clients:
    auth: AuthClient
    files: FilesClient
    invoice_ingestor: InvoiceIngestorClient
    guardrails: GuardrailsClient
    llm: LlmGatewayClient
    mcp: McpGatewayClient
    prompts: PromptsClient | None      # registry is a plain module; client optional — omit if unused
    tools: ToolsClient
    sessions: SessionsClient
    orchestrator: OrchestratorClient
    payments: PaymentsClient

async def build_clients(settings: Settings, pools: Pools, checkpointers: Checkpointers) -> Clients:
    ...  # repos first, then services, then clients; only place anything is instantiated
```

- `backend/api/__init__.py`, `app.py`:

```python
def create_app() -> FastAPI:
    app = FastAPI(title="Blinka API", lifespan=lifespan)
    app.add_exception_handler(RequestValidationError, _reject_invalid_request)
    app.add_exception_handler(GuardrailRejectionError, _reject_unsafe_input)   # 422
    app.add_exception_handler(InvalidCredentialsError, ...)                     # 401
    app.include_router(api_router)
    return app

app = create_app()
```

`lifespan`: create 3 engines + sessionmakers (PG-1/PG-2/PG-3 DSNs) → open both checkpointers (async ctx) → `await checkpointer.setup()` ×2 → `build_clients` → bucket bootstrap (FilesService) → `fail_unfinished` sweep (PaymentsService) → `app.state.settings/clients/pools` → yield → dispose engines, close checkpointers.

- `backend/api/deps.py` — `get_settings`, `get_clients` (from `request.app.state`), `get_current_user` (JWT decode → `CurrentUser` contract; concrete impl in auth module, dep wired there), `CurrentUserDep`, `ClientsDep = Annotated[Clients, Depends(get_clients)]`.
- `backend/api/routers/__init__.py` — `api_router = APIRouter()`; `GET /health` → `{"status": "ok"}`; includes the per-domain routers (`auth`, `chat`, `files`, `payments`). All routers except health/auth get `dependencies=[Depends(get_current_user)]`.
- `backend/api/routers/auth.py`, `chat.py`, `files.py`, `payments.py` — one file per HTTP domain; each owns its endpoints AND its router-specific dependencies (declared inline). `modules/` NEVER imports FastAPI — routers are the only place `APIRouter`/`Depends`/`UploadFile` appear.
- `backend/.env.example` — every var with local-dev defaults (see 03-docker-stack for the exact values).

## Implementation Guidelines

- Import style everywhere: `from contracts.payments import PaymentRunAccepted` (top-level packages, run from `backend/`).
- No global mutable state besides `app = create_app()`.
- `Clients` fields may start as `None`-free — all 11 modules exist by the end of this plan; if implementing skeleton-first, type fields with the client classes and let 12-stub-modules provide them.

## Dependencies

01-monorepo-restructure.

## Integration Notes

`api.app:app` is the uvicorn target referenced by `backend/package.json`, Dockerfile CMD, and README commands. `Clients` is the contract every module spec wires into.
