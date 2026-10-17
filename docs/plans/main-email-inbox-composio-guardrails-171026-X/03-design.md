# Technical Design

Backend paths are relative to `backend/` and frontend paths are relative to `frontend/`.

## Architecture Decisions

1. **`modules/mail_gateway` is the Composio adapter and the only importer of `composio`.**
   - Every SDK call goes through `asyncio.to_thread`, because the SDK is sync.
   - It returns contracts from `contracts/mail_gateway.py` and never exposes raw SDK objects.
2. **`modules/inbox` owns mailbox connections, emails and the email pipeline.** It reaches other modules only through these clients: `auth`, `files`, `guardrails`, `payments` and `mail_gateway`.
3. **Background execution uses an in-process `ExecutionRegistry`, moved to `core/background.py`.**
   - Payments keeps its own instance; inbox gets a second one.
   - There is no broker. A restart sweep marks unfinished work as failed.
4. **The webhook is public and authenticated by signature.**
   - Verification: `Composio.triggers.parse(body=raw_bytes, headers=..., verify_secret=COMPOSIO_WEBHOOK_SECRET)`.
   - A failed signature raises `WebhookSignatureError`, which maps to 401.
   - Non-message events and unknown connected accounts are logged and acknowledged with 202.
5. **The guardrail is `ApplyGuardrail(source="INPUT")` on untrusted text only.**
   - Text is split into chunks of at most 25,000 characters and checked in order. The email is blocked at the first chunk with BLOCKED assessments.
   - `enforce=False` keeps the current pass-through behaviour.
   - AWS errors raise `GuardrailUnavailableError`, which maps to 503 on HTTP and to `error` in the pipeline.
6. **The invoice always reaches payments as a file.**
   - It is either the first PDF attachment or the body saved as `text/plain`.
   - `PaymentRunTrigger(file_id)` and `run_execution` keep their signatures.
7. **The payment agent is repurposed (TEMPORAL).**
   - Tools: `get_invoice_context` and `convert_to_clp`.
   - Structured output: `InvoiceClpAnalysis` via `ToolStrategy`.
   - The runner stores `{"summary", "analysis"}` in the `completed` event.
8. **The displayed status is derived at read time.**
   - The stored `inbox_emails.status` is `received | processing | blocked | analyzing | error`.
   - When the stored status is `analyzing`, the view status comes from the run:
     - `completed` with `analysis.is_invoice` → `analyzed`
     - `completed` without `is_invoice` → `no_invoice`
     - `failed` with an `invoice_parse_failed` event → `no_invoice`
     - `failed` otherwise → `error`
     - `pending` or `running` → `analyzing`
9. **CORS is configured in `create_app()`** from `CorsSettings()`. That is a standalone `BaseSettings`, so `create_app` doesn't need DB URLs.

## Patterns & Conventions

- **Module layout:** mirror `modules/files/`: an `__init__.py` facade with an alphabetized `__all__`, `errors.py`, `service.py`, `repository.py` and `models.py`.
- **External adapter:** mirror `modules/files/storage.py`:
  - a lazily entered aioboto3 client (`self._client_context.__aenter__()`)
  - `raise XError from error`
- **Client facades:** mirror `clients/files.py`. Import the service under `TYPE_CHECKING`, use string annotations, and pass calls straight through.
- **Cross-module dependencies:** inject clients through the constructor and import them under `TYPE_CHECKING`, as in `modules/invoice_ingestor/service.py:14-17`.
- **Background entrypoint:** mirror `modules/payments/runner.py::run_execution`:
  - a frozen `@dataclass` of dependencies
  - `try / except asyncio.CancelledError: ...; raise / except Exception: logger.exception(...)`
- **Repositories:** mirror `modules/files/repository.py`:
  - `async with self._sessionmaker() as session`
  - a `_to_<contract>()` mapper
  - return `None` when not found, and let the service raise the error
- **Upsert and dedupe:** use `sqlalchemy.dialects.postgresql.insert(...).on_conflict_do_nothing(...)`, as in `modules/invoice_ingestor/repository.py`.
- **Errors:** one base class per module, `XError(Exception): pass`. HTTP mapping goes in `api/app.py::create_app` through private `_reject_*` handlers.
- **Logging:** `logger = get_logger(__name__)` with snake_case event names and keyword fields, e.g. `logger.info("inbox_email_received", email_id=...)`.
- **Constants:** module-level UPPER_SNAKE names.
- **Comments:** none, except the `# TEMPORAL: ...` markers on the repurposed payment agent, which the user asked for.
- **Contracts:**
  - `StrictModel` for internal data, `ApiModel` for HTTP and LLM-structured outputs (like `HelloWorldReport`).
  - `StrEnum` members are UPPER_SNAKE with lowercase values.
- **Settings:** each group is its own `BaseSettings` with prefix `BLINKA_<GROUP>__`. Third-party keys use `validation_alias`, as in `LlmSettings.api_key`.
- **Migrations:** autogenerate only: `cd backend && uv run alembic -n product revision --autogenerate -m "create inbox tables"`.
- **Frontend:** follow Next 16 App Router, React 19 client components and Tailwind v4 utility classes. Invoke the `frontend-design` skill while building pages.

## Dependencies

- `composio==0.28.0` and `composio-client==2.0.0rc17`.
  - Install with `uv add "composio==0.28.0" "composio-client==2.0.0rc17"`. The explicit pin is what lets uv accept the pre-release client.
  - **Never** use `--prerelease=allow`: it pulls `httpx 1.0.dev6`, which breaks on import.
  - The SDK is sync and pulls `openai`, `pysher` and `requests`.
- `httpx>=0.28`: move it from the dev group to main dependencies (already locked at 0.28.1).
- Already present: `aioboto3==15.5.0` (botocore 1.40.61, which has `apply_guardrail`, `tierConfig` and `crossRegionConfig`), `deepagents 0.7.28`, `langchain 1.4.6` (`ToolStrategy`) and `pypdf`.
- `boto3` (transitive, 1.40.61) is used only by `scripts/create_guardrail.py`.
- Frontend: no new packages (`next 16.4.2`, `react 19.3.1`, `tailwindcss 4.3.3`).

## Integration Points

| Location | Change |
|---|---|
| `core/config.py::Settings` | Remove `guardrails_enforce`. Add `guardrails: GuardrailsSettings` and `composio: ComposioSettings`. Add a standalone `CorsSettings`. |
| `core/background.py` (new) | `ExecutionRegistry`, moved verbatim from `modules/payments/runner.py:33-54`. Log key `task_id`, event `background_task_crashed`. |
| `modules/payments/runner.py` | Import `ExecutionRegistry` from `core.background`. Repurposed `_pay_invoice` (TEMPORAL). |
| `modules/payments/__init__.py` | Re-export `ExecutionRegistry` from `core.background`, so `container.py` imports keep working. |
| `modules/payments/agent.py::build_payment_agent` | Tools become `[get_invoice_context, convert_to_clp]`. New `response_schema` param fed to `ToolStrategy`. |
| `modules/payments/service.py::get_run` | Fill `PaymentRunStatus.analysis` from the latest `completed` event's `payload["analysis"]`. |
| `modules/prompts/payment_agent.py` | New prompt text (TEMPORAL). `response_schema = InvoiceClpAnalysis`. |
| `modules/prompts/invoice_extraction.py` | Add the Chilean invoice rules. |
| `modules/guardrails/service.py` | `GuardrailsService(settings: GuardrailsSettings, backend: GuardrailBackend)`. `check()` calls the backend when `enforce`. |
| `modules/guardrails/bedrock.py` (new) | `BedrockGuardrailBackend`. |
| `modules/auth/service.py` + `clients/auth.py` | Add `get_user(user_id) -> CurrentUser`, which raises `UserMissingError`. |
| `container.py` | Add `mail_gateway: MailGatewayClient` and `inbox: InboxClient` to `Clients`. Build guardrails with the Bedrock backend. Build inbox after payments. |
| `api/app.py::lifespan` | After the payments sweep: `await clients.inbox.fail_unfinished(RESTART_INTERRUPTION_REASON)`. On shutdown: `await clients.inbox.shutdown()`. |
| `api/app.py::create_app` | Add `CORSMiddleware`. Add handlers: `GuardrailUnavailableError` → 503, `WebhookSignatureError` → 401, `MailboxConnectionMissingError` / `EmailMissingError` → 404, `MailboxAlreadyConnectedError` → 409, `MailProviderError` → 502. |
| `api/routers/__init__.py` | `include_router(webhooks.webhooks_router)` is public. `include_router(inbox.inbox_router, dependencies=[Depends(get_current_user)])`. |
| `alembic/env.py` (product branch) | `import modules.inbox.models  # noqa: F401` |
| `.env.example` | Add the new keys (see below). |

## Data Structures

### Settings (`core/config.py`)

```python
class GuardrailsSettings(BaseSettings):      # env_prefix="BLINKA_GUARDRAILS__"
    enforce: bool = False
    guardrail_id: str = ""
    guardrail_version: str = "DRAFT"
    aws_profile: str | None = None            # .env: panoptico
    aws_region: str = "us-east-1"

class ComposioSettings(BaseSettings):        # env_prefix="BLINKA_COMPOSIO__"
    api_key: SecretStr = Field(validation_alias="COMPOSIO_API_KEY", default=SecretStr(""))
    webhook_secret: SecretStr = Field(validation_alias="COMPOSIO_WEBHOOK_SECRET", default=SecretStr(""))
    gmail_auth_config_id: str = ""
    outlook_auth_config_id: str = ""
    gmail_toolkit_version: str = "20261015_00"
    outlook_toolkit_version: str = "20261014_00"
    gmail_poll_interval_minutes: int = 15
    callback_url: str = "http://localhost:3000/inbox/callback"

class CorsSettings(BaseSettings):            # env_prefix="BLINKA_CORS__"
    allow_origins: list[str] = ["http://localhost:3000"]
```

New `.env.example` keys:
- `BLINKA_GUARDRAILS__ENFORCE`, `BLINKA_GUARDRAILS__GUARDRAIL_ID`, `BLINKA_GUARDRAILS__GUARDRAIL_VERSION`, `BLINKA_GUARDRAILS__AWS_PROFILE`, `BLINKA_GUARDRAILS__AWS_REGION`
- `COMPOSIO_API_KEY`, `COMPOSIO_WEBHOOK_SECRET`
- `BLINKA_COMPOSIO__GMAIL_AUTH_CONFIG_ID`, `BLINKA_COMPOSIO__OUTLOOK_AUTH_CONFIG_ID`
- `BLINKA_CORS__ALLOW_ORIGINS`

Remove `BLINKA_GUARDRAILS_ENFORCE`.

### `contracts/mail_gateway.py` (new, internal)

```python
class MailProvider(StrEnum):
    GMAIL = "gmail"
    OUTLOOK = "outlook"
    SIMULATED = "simulated"

class MailAccountStatus(StrEnum):
    INITIATED = "initiated"
    ACTIVE = "active"
    FAILED = "failed"
    EXPIRED = "expired"

class MailboxLink(StrictModel):
    connected_account_id: str
    redirect_url: str

class MailTriggerEvent(StrictModel):
    provider: MailProvider
    connected_account_id: str
    message_id: str
    data: dict

class FetchedAttachment(StrictModel):
    filename: str
    mime: str
    content: bytes

class FetchedEmail(StrictModel):
    sender: str
    subject: str
    body: str
    received_at: datetime | None = None
    attachments: list[FetchedAttachment] = []
```

### `contracts/inbox.py` (new)

```python
class InboxEmailStatus(StrEnum):
    RECEIVED = "received"
    PROCESSING = "processing"
    BLOCKED = "blocked"
    ANALYZING = "analyzing"
    ANALYZED = "analyzed"
    NO_INVOICE = "no_invoice"
    ERROR = "error"

class SimulatedEmailKind(StrEnum):
    INVOICE_USD = "invoice_usd"
    INVOICE_CLP = "invoice_clp"
    PROMPT_INJECTION = "prompt_injection"
    PLAIN = "plain"

class ConnectMailboxRequest(ApiModel):
    provider: Literal[MailProvider.GMAIL, MailProvider.OUTLOOK]

class MailboxConnectStarted(ApiModel):
    connection_id: UUID
    redirect_url: str

class ConfirmMailboxRequest(ApiModel):
    connected_account_id: str

class MailboxConnectionView(ApiModel):
    connection_id: UUID
    provider: MailProvider
    status: MailAccountStatus
    created_at: datetime

class SimulateEmailRequest(ApiModel):
    kind: SimulatedEmailKind

class InboxEmailView(ApiModel):
    email_id: UUID
    provider: MailProvider
    sender: str
    subject: str
    preview: str                 # first 140 chars of body
    received_at: datetime | None
    status: InboxEmailStatus
    analysis: InvoiceClpAnalysis | None = None

class InboxEmailDetail(InboxEmailView):
    body: str
    violations: list[GuardrailViolation] = []
    error: str | None = None
    run_id: UUID | None = None

class InboxEmailRecord(StrictModel):   # repository → service
    email_id: UUID
    owner_id: UUID
    provider: MailProvider
    sender: str
    subject: str
    body: str
    received_at: datetime | None
    status: InboxEmailStatus
    violations: list[GuardrailViolation]
    run_id: UUID | None
    error: str | None

class MailboxConnectionRecord(StrictModel):
    connection_id: UUID
    owner_id: UUID
    provider: MailProvider
    connected_account_id: str
    trigger_id: str | None
    status: MailAccountStatus
    created_at: datetime
```

### `contracts/payments.py` (additions)

```python
class ClpConversion(StrictModel):
    amount: float
    currency: str
    clp_rate: float
    amount_clp: float

class InvoiceClpAnalysis(ApiModel):
    """Final step: call this exactly once with the invoice analysis expressed in CLP."""
    is_invoice: bool
    vendor: str | None = None
    invoice_number: str | None = None
    original_amount: float | None = None
    original_currency: str | None = Field(default=None, description="ISO 4217 code; UF is CLF.")
    clp_rate: float | None = Field(default=None, description="The clp_rate returned by convert_to_clp.")
    amount_clp: float | None = Field(default=None, description="The amount_clp returned by convert_to_clp.")
    summary: str = Field(description="One or two sentences in Spanish for the inbox.")

class PaymentRunStatus(ApiModel):   # existing + 1 field
    ...
    analysis: InvoiceClpAnalysis | None = None
```

### Tables (product DB, `ProductBase`)

```
mailbox_connections
  id                    UUID PK default uuid4
  owner_id              UUID FK users.id, index
  provider              str                      -- gmail | outlook
  connected_account_id  str unique               -- Composio ca_…
  trigger_id            str | None               -- Composio ti_…
  status                str default "initiated"
  created_at            datetime server_default now()
  updated_at            datetime server_default now(), onupdate now()

inbox_emails
  id                    UUID PK default uuid4
  owner_id              UUID FK users.id, index
  connection_id         UUID | None FK mailbox_connections.id   -- null for simulated
  provider              str
  external_message_id   str
  sender                str default ""
  subject               str default ""
  body                  Text default ""
  received_at           datetime | None
  status                str default "received", index
  violations            JSONB default list
  file_id               UUID | None FK files.id
  run_id                UUID | None FK agent_runs.id
  error                 str | None
  created_at / updated_at as above
  UniqueConstraint(provider, external_message_id)
```
