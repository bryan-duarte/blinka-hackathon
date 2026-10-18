# Technical Design

## Architecture Decisions

1. **Triggers call payments directly, and no orchestrator exists.** The entry points are:
   - `InboxService.ingest_webhook`, `ingest_whatsapp_webhook` and `simulate`, which go through `process_email` and then `PaymentsService.start_run`.
   - `POST /payments/runs`, which calls `start_file_run`.

   `start_run` spawns `runner.run_execution`, which now runs the payments deep agent.
2. **The payments agent is a deep agent over deterministic step tools.**
   - It is built with `deepagents.create_deep_agent(model=llm.model("payments"), tools=<6 step tools>, system_prompt=PAYMENTS_AGENT, middleware=[TodoListMiddleware()], checkpointer=checkpointers.payments)`.
   - Tools are closures over a per-run mutable `RunState`.
   - Each tool enforces its preconditions and returns a short error string when called out of order.
   - Verdicts come only from `rules.decide`, `apply_checker` and `settle`.
3. **Fail closed.** After `agent.astream_events` finishes, or raises, `run_execution` inspects `RunState`:

   | `RunState` after the agent | Action |
   |---|---|
   | `decision` set, or `terminal_reason` (`not_a_bill` / `extraction_failed`) | Completed |
   | `claim` set but no `decision` | Record the `decision_failed` event, call `fail_closed`, then complete |
   | Anything else | Record the `failed` event with `{"error": "agent_incomplete"}` and set `RunStatus.FAILED` |

   The run config is `{"recursion_limit": 40, **thread_config(str(run_id))}`.
4. **One realtime choke point per domain.**
   - Payments: `RunEventRecorder` (`modules/payments/events.py`). It persists through `RunsRepository.insert_event`, which now returns the row id, then publishes.
   - Inbox: `InboxNotifier` (`modules/inbox/notifier.py`). It publishes after each status mutation.
   - Both go through `RealtimeClient.publish(owner_id, events)`.
   - Publishing is best effort: errors are logged as `realtime_publish_failed` and never raised.
5. **AppSync Events transport.**
   - The backend publishes with HTTP POST to `https://{http_domain}/event`, SigV4-signed (service `appsync`). Credentials come from `aioboto3.Session(profile_name=settings.realtime.aws_profile or None)`, i.e. the default chain: profile now, instance role later.
   - Each POST carries at most 5 events, and each serialized event must be ≤ 240 KB (truncate payload strings to `REALTIME_MAX_TEXT_CHARS = 2000`).
   - When `BLINKA_REALTIME__ENABLED=false` or `http_domain` is empty, `NullRealtimeBackend` is used.
6. **Channel** = `/{namespace}/{owner_id}` with namespace `inbox`. Clients subscribe with an API key.
7. **WhatsApp reuses the inbox tables and pipeline.**
   - A new `whatsapp_gateway` module (a Kapso httpx client) mirrors `mail_gateway`.
   - `process_email` accepts `WhatsAppDocumentEvent`, and `_resolve_email` dispatches by type.
   - `source_type` is derived from the provider via `SOURCE_TYPE_BY_PROVIDER`.
8. **Two WhatsApp modes per user** (`mailbox_connections.mode`):

   | Mode | `connected_account_id` | Inbound routing |
   |---|---|---|
   | `sandbox` (default) | `sandbox:{e164}` | Shared `settings.kapso.sandbox_phone_number_id`, matched by sender phone |
   | `own_number` (opt-in) | `setup:{setup_link_id}` until confirmed, then Kapso `phone_number_id` | Matched by `phone_number_id` |

   Confirming an own number sets the user's active sandbox row to `expired`.
9. **Infra changes.** The agent DB is removed. Sessions are removed. The payments DB keeps the LangGraph checkpointer tables, which `AsyncPostgresSaver.setup()` creates.

## Patterns & Conventions

- **Layering.** Contract in `contracts/<x>.py` (`StrictModel` internal, `ApiModel` API). Module in `modules/<x>/` (`service.py`, `errors.py`, `__init__.py` with `__all__`). Facade in `clients/<x>.py`, importing the service under `TYPE_CHECKING`. Wiring in `container.py:build_clients`. Mirror `mail_gateway` (`contracts/mail_gateway.py`, `modules/mail_gateway/service.py`, `clients/mail_gateway.py`, `container.py:84`).
- **Settings.** Mirror `ComposioSettings` in `core/config.py:75-89`: an un-prefixed alias for secrets (`KAPSO_API_KEY`, `KAPSO_WEBHOOK_SECRET`), with `BLINKA_KAPSO__*` and `BLINKA_REALTIME__*` for everything else, all nested in `Settings`. Document every variable in `backend/.env.example`.
- **Errors.** One base `<Module>Error` with empty subclasses. Register HTTP mappings in `api/app.py` `DOMAIN_ERROR_RESPONSES` (`:47-70`). Wrap third-party errors with `raise X from error`.
- **Logging.** `logger = get_logger(__name__)`, snake_case events with kwargs only (`modules/inbox/service.py:119`).
- **External HTTP.**
  - Use `httpx.AsyncClient(timeout=30)`, created per call, as `mail_gateway/service.py:212-218` does.
  - Catch `httpx.HTTPError`, then raise `WhatsAppProviderError`.
  - For AWS, use the aioboto3 lazy-context pattern from `modules/document_vision/textract.py:23-39`. The SigV4 credentials can be obtained from the aioboto3 session.
- **Webhooks.** Unauthenticated router in `api/routers/webhooks.py`. Pass the raw `await request.body()` and `request.headers` to the service. Idempotency via the DB unique constraint plus `on_conflict_do_nothing` (`modules/inbox/repository.py:73-96`).
- **Background work.** Use `ExecutionRegistry.spawn` (`core/background.py:15`).
- **Migrations.** Autogenerate with `uv run alembic -n product revision --autogenerate -m "..."` and `-n payments`. Product head today is `3838b3ca9de4`. **Review each payments autogenerate and delete any op touching `checkpoint*` tables.**
- **Frontend.**
  - `"use client"` pages, local `useState`, `api.*` in `useEffect` with an `isCancelled` flag (`frontend/src/app/inbox/page.tsx:83-133`).
  - Lookup tables as `Record<Enum, …>` in `lib/labels.ts`.
  - Hand-mirrored types in `lib/types.ts`.
  - Class constants from `components/settings/styles.ts`.
  - Read `frontend/DESIGN.md` fully before any UI change and follow it strictly. It is replaced often, so always use the latest version: paper canvas, cobalt accent only, weight 300, 4px radius, no shadows.
  - Read `frontend/node_modules/next/dist/docs/` before Next-specific code, as `frontend/AGENTS.md` requires.
- **UI copy** is Spanish and channel-neutral.

## Dependencies

| Package | Version | Where |
|---|---|---|
| deepagents | 0.7.28 (already locked) | backend |
| langchain (`langchain.agents.middleware.TodoListMiddleware`) | 1.4.6 (already locked, transitive) | backend |
| httpx | already present | backend (Kapso + AppSync publish) |
| aioboto3 / botocore | 15.5.0 / 1.40.61 (already present) | backend (SigV4) |
| aws-amplify | **6.22.2** (new) | frontend |
| hashicorp/aws | `~> 6.0`, locked 6.69.1; requires ≥ 6.9 for `aws_appsync_api` | infra |

No new Python dependencies.

## Integration Points

| Where | What changes |
|---|---|
| `backend/container.py:73-183` | Remove orchestrator, sessions and tools. Add `realtime`, `whatsapp_gateway`. Pass `checkpointers.payments`, `realtime` into `PaymentRunDependencies`. Pass `realtime` and `whatsapp_gateway` into `InboxDependencies`. Pass `settings.kapso` into `InboxService`. |
| `backend/api/app.py:73-104` | Lifespan: `Checkpointers(payments_url)` only. Drop `pools.agent`. Error handlers: remove `AgentProviderError` and `SessionMissingError`; add the WhatsApp errors. |
| `backend/api/routers/__init__.py` | Drop `chat` and `diagnostics`. |
| `backend/api/routers/webhooks.py` | Add `POST /webhooks/whatsapp`. |
| `backend/api/routers/inbox.py` | Add `POST /inbox/whatsapp/sandbox`, `POST /inbox/whatsapp/own-number`, `POST /inbox/whatsapp/confirm`. Add `source` query param on `GET /inbox/emails`. `SimulateEmailRequest.channel`. |
| `backend/modules/payments/runner.py:39-212` | Rewritten around the agent, plus `RunState` and `RunEventRecorder`. |
| `backend/modules/payments/settlement.py` | No change. It emits no run events (verified), and `settle` / `record_duplicate` / `fail_closed` are called unchanged from the tools and the runner. |
| `backend/modules/payments/repository.py:98-110` | `insert_event` returns `PaymentRunEvent` (with `id`). `list_events` maps `id`. `RUN_EVENT_LIST_LIMIT` goes from 100 to 300, because tool and todo events add about 30 rows per run. |
| `backend/modules/inbox/pipeline.py:49-164` | `InboxDependencies` gains `whatsapp_gateway` and `notifier`. `_resolve_email` dispatches by type. `_bill_source_intake` uses `SOURCE_TYPE_BY_PROVIDER`. |
| `backend/modules/inbox/service.py` | `ingest_whatsapp_webhook`, `register_whatsapp_sandbox`, `start_whatsapp_connection`, `confirm_whatsapp_connection`. `simulate(kind, channel)`. `_to_email_view` derives `source_type`. |
| `backend/modules/bills/service.py:32` | `WHOLE_CONTENT_HASHED_SOURCES` adds `BillSourceType.WHATSAPP`. |
| `frontend/src/app/inbox/page.tsx` | Realtime subscription, adaptive polling, source filter, WhatsApp simulate options. |
| `frontend/src/components/inbox/EmailDetail.tsx:73-83` | Replace `RunTimeline` with `AgentActivity`. |
| `frontend/src/components/inbox/ConnectionBar.tsx` | Render `WhatsAppCard`. |

## Data Structures

### Realtime (`backend/contracts/realtime.py`, new)

```python
class RealtimeEventType(StrEnum):
    INBOX_ITEM = "inbox.item"        # status change or new item
    RUN_STEP = "run.step"            # started/classified/extracted/claimed/decided/completed/failed/...
    AGENT_TOOL = "agent.tool"        # tool_started / tool_finished
    AGENT_TODOS = "agent.todos"      # write_todos snapshot
    AGENT_THINKING = "agent.thinking"  # coalesced token delta (never persisted)

class RealtimeEvent(StrictModel):
    type: RealtimeEventType
    item_id: UUID | None = None      # inbox_emails.id
    run_id: UUID | None = None
    step: str                        # run step name, inbox status, or tool phase
    payload: dict = {}
    message: str | None = None       # friendly Spanish text (tools, steps)
    sequence: int | None = None      # agent_run_events.id when persisted
    created_at: datetime
```

Wire format: `RealtimeEvent.model_dump_json()` is the string inside `events[]`.

### Persisted run steps (`agent_run_events.step`) — new values

| step | payload |
|---|---|
| `todos_updated` | `{"todos": [{"content": str, "status": "pending"\|"in_progress"\|"completed"}]}` |
| `tool_started` | `{"tool": str, "call_id": str, "message": str}` |
| `tool_finished` | `{"tool": str, "call_id": str, "message": str, "ok": bool, "duration_ms": int, "summary": str}` |
| `agent_summary` | `{"text": str}` (final AI message, ≤ 2000 chars) |

The existing steps (`started`, `classified`, `not_a_bill`, `extraction_failed`, `extracted`, `claimed`, `decided`, `decision_failed`, `completed`, `cancelled`, `failed`) are unchanged, and each now also carries `payload["message"]`.

`PaymentRunEvent` gains `id: int`:

```python
class PaymentRunEvent(StrictModel):
    id: int
    step: str
    payload: dict = {}
    created_at: datetime
```

### Payments agent run state (`backend/modules/payments/agent_state.py`, new)

```python
@dataclass
class RunState:
    run_id: UUID
    owner: CurrentUser
    source: BillSourceRecord
    document: BillDocument
    classification: BillClassification | None = None
    extraction: CandidateExtraction | None = None
    policy: PaymentPolicy | None = None
    match: PayeeMatch | None = None
    claim: BillClaim | None = None
    context: DecisionContext | None = None
    evaluation: RuleEvaluation | None = None
    assessment: CheckerAssessment | None = None
    decision: DecisionRecord | None = None
    terminal_reason: Literal["not_a_bill", "extraction_failed"] | None = None
```

### Kapso / WhatsApp (`backend/contracts/whatsapp_gateway.py`, new)

```python
class WhatsAppConnectionMode(StrEnum):
    SANDBOX = "sandbox"
    OWN_NUMBER = "own_number"

class WhatsAppDocumentEvent(StrictModel):
    phone_number_id: str          # Kapso/Meta id of the receiving number
    message_id: str               # wamid (inbox_emails.external_message_id)
    sender_phone: str             # E.164 normalized, "+56912345678"
    contact_name: str | None
    filename: str
    mime: str                     # from EVIDENCE_MIME_BY_EXTENSION by extension
    caption: str = ""
    media_url: str | None         # message.kapso.media_url or media_data.url
    media_id: str | None          # message.document.id
    received_at: datetime | None

class SandboxActivation(StrictModel):
    activation_code: str
    activation_link: str

class KapsoSetupLink(StrictModel):
    setup_link_id: str
    url: str

class KapsoPhoneNumber(StrictModel):
    phone_number_id: str
    customer_id: str | None
    display_phone_number: str
    is_coexistence: bool
    status: str

# API
class RegisterSandboxRequest(ApiModel):
    phone_number: str  # any format; normalized server side to E.164

class WhatsAppSandboxView(ApiModel):
    connection_id: UUID
    phone_number: str
    sandbox_number: str           # settings.kapso.sandbox_display_number
    activation: SandboxActivation | None   # None → manual fallback
    status: MailAccountStatus

class ConfirmWhatsAppRequest(ApiModel):
    setup_link_id: str
    phone_number_id: str
```

### Contracts changes

- `contracts/mail_gateway.py`: `MailProvider` adds `WHATSAPP = "whatsapp"`.
- `contracts/inbox.py`:
  - `MailboxConnectionView` adds `mode: WhatsAppConnectionMode | None = None`, `phone_number: str | None = None`.
  - `SimulateEmailRequest` adds `channel: Literal["email", "whatsapp"] = "email"`.
  - `InboxSourceFilter = Literal["email", "whatsapp"]`.
  - New `SOURCE_TYPE_BY_PROVIDER: dict[MailProvider, BillSourceType]`, mapping gmail/outlook/simulated to EMAIL and whatsapp to WHATSAPP.
  - `MailboxConnectionRecord` adds `mode: str | None`, `phone_number: str | None`, `external_ref: str | None`.
- `contracts/payments.py`: drop `PaymentRunTrigger.session_id`. `PaymentRunEvent.id`.
- `contracts/prompts.py`: remove `MAIN_AGENT`, `HELLO_WORLD`, `HelloWorldReport`. Add `PAYMENTS_AGENT`.
- Delete `contracts/chat.py`, `contracts/sessions.py`, `contracts/tools.py`.

### DB changes (product)

- `mailbox_connections`:
  - `+ mode String NULL`
  - `+ phone_number String NULL`
  - `+ external_ref String NULL` (Kapso customer id)
  - `+ partial unique index uq_mailbox_connections_sandbox_phone ON (phone_number) WHERE mode='sandbox' AND status='active'`
- `agent_runs`: `- session_id` (FK and column).
- `sessions`: dropped.

### DB changes (payments)

- `session_executions`: dropped.

### Settings (`backend/core/config.py`)

```python
class KapsoSettings(BaseSettings):   # env_prefix="BLINKA_KAPSO__"
    api_key: SecretStr = Field(validation_alias="KAPSO_API_KEY", default=SecretStr(""))
    webhook_secret: SecretStr = Field(validation_alias="KAPSO_WEBHOOK_SECRET", default=SecretStr(""))
    base_url: str = "https://api.kapso.ai"
    webhook_url: str = ""                      # public https URL of /webhooks/whatsapp
    callback_url: str = "http://localhost:3000/inbox/whatsapp/callback"
    sandbox_phone_number_id: str = ""
    sandbox_display_number: str = ""

class RealtimeSettings(BaseSettings):  # env_prefix="BLINKA_REALTIME__"
    enabled: bool = False
    http_domain: str = ""                      # terraform output events_http_domain
    region: str = "us-east-1"
    aws_profile: str | None = "panoptico"      # None → default credential chain (instance role)
    namespace: str = "inbox"
    thinking_flush_ms: int = 400

# Settings: + kapso, + realtime; - agent_database_url
```

### Frontend types (`frontend/src/lib/types.ts`)

```ts
export type MailProvider = "gmail" | "outlook" | "simulated" | "whatsapp";
export type ConnectableProvider = "gmail" | "outlook";
export type WhatsAppConnectionMode = "sandbox" | "own_number";
export type InboxSourceFilter = "email" | "whatsapp";
export type RealtimeEventType = "inbox.item" | "run.step" | "agent.tool" | "agent.todos" | "agent.thinking";
export type RealtimeEvent = {
  type: RealtimeEventType; item_id: string | null; run_id: string | null; step: string;
  payload: Record<string, unknown>; message: string | null; sequence: number | null; created_at: string;
};
export type AgentTodo = { content: string; status: "pending" | "in_progress" | "completed" };
export type SandboxActivation = { activation_code: string; activation_link: string };
export type WhatsAppSandboxView = { connection_id: string; phone_number: string; sandbox_number: string; activation: SandboxActivation | null; status: MailAccountStatus };
// MailboxConnectionView += mode: WhatsAppConnectionMode | null; phone_number: string | null
// PaymentRunEvent += id: number
```

### Env vars

| Var | Where | Source |
|---|---|---|
| `BLINKA_REALTIME__ENABLED`, `BLINKA_REALTIME__HTTP_DOMAIN`, `BLINKA_REALTIME__REGION`, `BLINKA_REALTIME__AWS_PROFILE` | backend/.env | terraform `events_http_domain` |
| `KAPSO_API_KEY`, `KAPSO_WEBHOOK_SECRET`, `BLINKA_KAPSO__WEBHOOK_URL`, `BLINKA_KAPSO__SANDBOX_PHONE_NUMBER_ID`, `BLINKA_KAPSO__SANDBOX_DISPLAY_NUMBER`, `BLINKA_KAPSO__CALLBACK_URL` | backend/.env | Kapso dashboard + `scripts/bootstrap_kapso.py` |
| `NEXT_PUBLIC_APPSYNC_EVENTS_ENDPOINT` (`https://{http_domain}/event`), `NEXT_PUBLIC_APPSYNC_EVENTS_REGION`, `NEXT_PUBLIC_APPSYNC_EVENTS_API_KEY` | frontend/.env.local | terraform outputs |
| `BLINKA_AGENT_DATABASE_URL` | **removed** | — |
