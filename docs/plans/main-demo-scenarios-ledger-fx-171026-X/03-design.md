# Technical Design

## Architecture Decisions

1. **Three new backend modules follow the modular-monolith layout.** Each has `contracts/<x>.py`, `clients/<x>.py`, `modules/<x>/{service,repository,models?,errors,__init__}.py`, a field on `container.Clients` and a router in `api/routers/`.
   - `fx` owns `fx_rates` and converts amounts to USD. It is consumed by `payments` through `PaymentRunDependencies.fx`.
   - `demo` holds the seed data, the document renderer, the scenario catalog, the sequencer and reset. It is consumed by `api/routers/demo.py` and the `lifespan`.
   - `accountability` is a read model for the ledger, the summary, the CSV export and the runs list.
   - `payment_policy` gains `trusted_forwarders` (07), a general policy feature that the demo seeds.
2. **`accountability` reads across modules on purpose.** Its repository runs owner-scoped SQL joins over `payment_decisions`, `bills`, `bill_sources`, `inbox_emails`, `payments`, `payees`, `agent_runs` and `agent_run_events`. A read-only report spanning tables is the one place where joining beats composing four clients. It imports ORM rows from the owning modules and never writes.
3. **`demo` writes across modules on purpose, for seed and reset only.** `DemoSeedRepository` inserts backdated history rows (`bills`, `payment_decisions`, `payments`, `budget_counters`) directly, because the live services stamp `now()` and enforce state transitions. `DemoResetRepository` deletes everything an owner has in one product-DB transaction, in FK order. The policy, payees and blacklist are seeded through `PaymentPolicyClient` so they go through validation.
4. **Scenarios go through the real pipeline.** `InboxService.simulate(kind, channel)` is replaced by `InboxService.inject(owner, message: FetchedEmail, channel: InboxChannel) -> InboxEmailView`, which has the same body minus the `SIMULATED_EMAILS` lookup. `modules/inbox/samples.py`, `SimulatedEmailKind`, `SimulateEmailRequest`, `WHATSAPP_SIMULATABLE_KINDS`, `POST /inbox/simulate` and `WhatsAppSimulationUnsupportedError` are all deleted. `as_whatsapp_message` moves to `modules/demo/catalog.py`.
5. **Sequencing runs in the background, with state in memory.** `DemoService.launch` creates a `DemoLaunch` held in `dict[UUID, DemoLaunch]` and spawns `_run_sequence` on its own `ExecutionRegistry` keyed by owner. Each step does `inbox.inject`, then polls `inbox.get_email` every `SEQUENCE_POLL_SECONDS = 1.0` until the status is terminal or `STEP_TIMEOUT_SECONDS = 150` passes. Launch state is lost on restart, which is acceptable for a demo.
6. **Launches are repeatable without a reset.** Every scenario builder receives a `LaunchContext(today: date, nonce: int)`, and invoice numbers embed `nonce` (e.g. `INV-2050-{nonce:03d}`). Steps in the same sequence share it. `nonce = secrets.randbelow(9000) + 1000`, drawn once per launch. The exception is `dup_against_history`, which uses a fixed number that matches a seeded bill.
7. **FX is quoted once, stored on the bill and reused everywhere.**
   - `FxService.quote(currency, on)` is called inside `PaymentStepTools._register_bill`, before `_bill_fields`.
   - `BillFields`/`bills` carry `amount_usd`, `fx_usd_per_unit`, `fx_rate_date` and `fx_source`.
   - `context_builder.build_context` and `rebuild_context` use `bill.amount_usd` instead of recomputing `to_usd`.
   - `settlement._pay` copies the FX fields into `ReservationRequest` and then into `payments`.
   - `modules/payments/fx.py` loses `DUMMY_USD_PER_UNIT` and `to_usd` (the table moves to `modules/fx/static_rates.py`), and keeps `names_currency_explicitly`, `EXPLICIT_CURRENCY_MARKERS` and `current_period`.
8. **The FX lookup order is fixed.** `FxSource` resolves in this order:
   1. `USD` returns identity.
   2. A stored `fx_rates` row for `on` with source `open_er_api`.
   3. A live fetch with a 2 s timeout, inserting all currencies for the provider's update date.
   4. The latest stored row within `max_stale_days=7`, returned as `cached`.
   5. `STATIC_USD_PER_UNIT`, returned as `static_fallback`.
   6. Otherwise `None`.

   An `asyncio.Lock` per `FxService` prevents parallel live fetches.
9. **Reset order is fixed.** Reset takes `DemoService._lock` and then:
   1. Cancels the demo sequencer tasks, then `inbox.cancel_owner(owner_id)`, then `payments.cancel_owner(owner_id)`.
   2. Collects `run_ids` and `storage_keys`.
   3. Runs `DemoResetRepository.purge_owner(owner_id)` in one transaction.
   4. Calls `payments.purge_run_threads(run_ids)` and `files.purge_owner_objects(owner_id)`. Both are best-effort and log on failure.
   5. Calls `DemoSeeder.seed(owner)`.
   6. Publishes an `inbox.item` event with `item_id=None` and `payload={"status": "reset"}` so open tabs refresh.

   Launch and reset return 409 `DemoBusyError` while the lock is held.
10. **The run trace comes from the checkpointer.** `PaymentsService.run_trace(owner, run_id)` checks ownership through `get_run`, then calls `checkpointer.aget_tuple(thread_config(run_id))` and serializes `checkpoint["channel_values"]["messages"]`. It is exposed at `GET /payments/runs/{run_id}/trace`. `None` or a missing checkpointer returns an empty `messages` list with `is_available=False`.
11. **The guardrail is secure by default.** `GuardrailsSettings.enforce: bool = True`. In `backend/.env`, the `BLINKA_GUARDRAILS_ENFORCE` key is renamed to `BLINKA_GUARDRAILS__ENFORCE`. `.env.example` documents the default-on behavior and how to opt out.
12. **The whole console is in English.** The frontend uses `lang="en"` and the `en-US` locale in `format.ts`. Backend user-facing strings move to English, and code identifiers stay as they are. Rule IDs and Spanish `RULE_NAMES` keys (`datos_completos`, …) become English snake_case (`complete_data`, …). They are only stored inside JSONB `rule_results.name`, which seeded data writes fresh and reset wipes.

## Patterns & Conventions

- Settings: nested `BaseSettings` with `env_prefix="BLINKA_<X>__"`, `env_file=".env"`, `extra="ignore"`, `frozen=True`, following `GuardrailsSettings` in `backend/core/config.py`.
- Contracts: `StrictModel` for internal records and `ApiModel` for API I/O (`backend/contracts/_base.py`). Enums are `StrEnum`. Money is `Decimal`, which goes over the wire as a string; the frontend type is `Decimal = string`.
- Routers: one-line handlers that delegate to `clients.<x>`, with `response_model=`, following `backend/api/routers/bills.py`. Register them in `api/routers/__init__.py` with `dependencies=[Depends(get_current_user)]`. The public `/demo/status` and `/demo/login` go on a second router without auth.
- Errors: one module base error with empty subclasses, mapped in `DOMAIN_ERROR_RESPONSES` in `backend/api/app.py`.
- Logging: `logger = get_logger(__name__)`, with snake_case events and kwargs context.
- Repositories: session per method, `postgresql.insert(...).returning(...)`, and `on_conflict_do_nothing` for idempotency (`backend/modules/payments/ledger_repository.py`).
- Magic values are UPPER_CASE module constants. Booleans use `is_`/`has_`.
- Migrations: `uv run alembic -n product revision --autogenerate -m "..."`, removing any `checkpoint*` ops. New model modules are imported in `backend/alembic/env.py`.
- Frontend:
  - Pages are `"use client"` and wrapped in `<ConsoleShell><ConsoleTopBar/>…</ConsoleShell>`.
  - Fetching goes through the `api` object in `frontend/src/lib/api.ts`.
  - Types are mirrored by hand in `frontend/src/lib/types.ts`, and labels live in `frontend/src/lib/labels.ts`.
  - Class constants come from `frontend/src/components/settings/styles.ts`.
  - **Re-read `frontend/DESIGN.md` fully before any UI work and follow its latest version strictly**, because it is replaced often.
  - Read `frontend/node_modules/next/dist/docs/` before writing Next-specific code (dynamic routes `/runs/[id]`, `params` handling).

## Dependencies

| Package | Where | Version | Why |
|---|---|---|---|
| `fpdf2` | backend `pyproject.toml` | latest 2.8.x, pinned exactly with `uv add fpdf2==<x>` | Styled invoice PDFs. Pulls in Pillow |
| `Pillow` | transitive via fpdf2 | — | Rasterizes the scanned-invoice image |
| `recharts` | frontend `package.json` | latest 3.x, exact version (check that the React 19 peer is satisfied) | Ledger charts |
| `httpx` | already present | — | open.er-api.com client |
| open.er-api.com | external HTTP | `GET https://open.er-api.com/v6/latest/USD` | No key needed. The response is `{"result":"success","time_last_update_unix":int,"rates":{"CLP":950.12,...}}` in units per USD |

## Integration Points

- `backend/core/config.py`: add `FxSettings` and `DemoSettings`, add the `Settings.fx` and `Settings.demo` properties (following how `settings.guardrails` is exposed), and change `GuardrailsSettings.enforce` to `True`.
- `backend/container.py`:
  - `build_clients` creates `FxClient(FxService(FxRepository(product_sessionmaker), OpenErApiProvider(settings.fx), settings.fx))` before payments and passes `fx=fx` into `PaymentRunDependencies`.
  - It creates `DemoClient(DemoService(...))` and `AccountabilityClient(AccountabilityService(AccountabilityRepository(product_sessionmaker), payments))`.
  - It adds the fields `fx`, `demo` and `accountability` to `Clients`.
- `backend/api/app.py` `lifespan`: after `recover_unfinished_payments` and `inbox.fail_unfinished`, `if settings.demo.enabled: await clients.demo.ensure_demo_account()`. On shutdown it calls `await clients.demo.shutdown()`. It also adds the new domain errors to `DOMAIN_ERROR_RESPONSES`.
- `backend/core/background.py` `ExecutionRegistry`: `spawn(task_id, execution, owner_id: UUID | None = None)` and `async cancel_owner(owner_id) -> int`.
- `backend/modules/payments/agent_tools.py`:
  - `_register_bill` awaits `self._dependencies.fx.quote(currency, today)`.
  - `_bill_fields(candidate, match, quote)` sets the FX fields.
- `backend/modules/payments/context_builder.py:51`: `amount_usd=bill.amount_usd`.
- `backend/modules/payments/settlement.py` `_pay`: `ReservationRequest(..., fx_usd_per_unit=bill.fx_usd_per_unit, fx_rate_date=bill.fx_rate_date, fx_source=bill.fx_source)`.
- `backend/modules/payments/rules.py` `_currency_allowed`: the reason when `amount_usd is None` becomes `f"No exchange rate available for {currency}; escalating."`.
- `backend/modules/payments/service.py`: add `run_trace`, `cancel_owner` and `purge_run_threads`. `PaymentsClient` mirrors them.
- `backend/modules/inbox/service.py`:
  - Replace `simulate` with `inject`.
  - Add `cancel_owner(owner_id)` delegating to the registry, and pass `owner_id` when spawning in `_accept`.
  - Add `get_email_status(owner, email_id) -> InboxEmailStatus`, built from `get_email` and its resolved status.
- `backend/modules/files/storage.py`: `StorageBackend.delete_prefix(prefix) -> int` uses ListObjectsV2 paginated plus DeleteObjects in batches of 1000. `FilesService.purge_owner_objects(owner_id)` calls it with `f"{owner_id}/"`.
- `backend/modules/payments/models.py` / `bills/models.py`: new FX columns.
- Frontend:
  - `frontend/src/components/console/ConsoleShell.tsx` `NAV_GROUPS` becomes:
    - "Payments": Inbox `/inbox`, Review queue `/bills`, Agent ledger `/ledger`, Executions `/runs`.
    - "Payment rules": Policy, Payees, Blacklist.
  - `frontend/src/app/inbox/page.tsx` removes `EMAIL_SIMULATION_OPTIONS`, `WHATSAPP_SIMULATION_OPTIONS`, `SIMULATION_GROUPS` and `simulate()`, and adds `<DemoScenariosPanel>`.
  - `frontend/src/app/login/page.tsx` gets the demo button.

## Data Structures

### Migration (product DB, new revision after `b72f0ef0a7a0`)

```text
fx_rates
  id               UUID PK default uuid4
  quote_currency   String(3)  not null          -- ISO code, e.g. "CLP"
  rate_date        Date       not null
  usd_per_unit     Numeric(20,10) not null
  source           String(24) not null          -- FxSource value
  fetched_at       timestamptz not null default now()
  UNIQUE uq_fx_rates_currency_date_source (quote_currency, rate_date, source)
  INDEX  ix_fx_rates_currency_date (quote_currency, rate_date)

trusted_forwarders
  id               UUID PK
  owner_id         UUID FK users, indexed
  kind             String(16) not null           -- "email" | "domain"
  normalized_value String not null
  note             String(120) null
  created_at       timestamptz not null default now()
  UNIQUE uq_trusted_forwarders_owner_kind_value (owner_id, kind, normalized_value)

bills     + fx_usd_per_unit Numeric(20,10) null, fx_rate_date Date null, fx_source String(24) null
payments  + fx_usd_per_unit Numeric(20,10) null, fx_rate_date Date null, fx_source String(24) null
```

### `backend/contracts/fx.py`

```python
class FxSource(StrEnum):
    IDENTITY = "identity"            # USD
    OPEN_ER_API = "open_er_api"
    CACHED = "cached"                # stored live rate older than `on`
    STATIC_FALLBACK = "static_fallback"
    SEED = "seed"                    # demo history

class FxQuote(StrictModel):
    currency: str                    # ISO 4217
    usd_per_unit: Decimal
    rate_date: date
    source: FxSource

    def convert(self, amount: Decimal) -> Decimal:  # quantize 0.01 ROUND_HALF_UP
        ...
```

### Bills / payments contracts (additions)

- `BillFields`, `BillRecord`, `PaymentRecord`, `ReservationRequest`: `fx_usd_per_unit: Decimal | None`, `fx_rate_date: date | None`, `fx_source: FxSource | None`.
- `BillDecisionView`, `PaymentView`: the same three fields, which the UI renders.

### `backend/contracts/demo.py`

```python
class DemoSectionId(StrEnum):
    HAPPY_PATH = "happy_path"; FORMATS = "formats"; DUPLICATES = "duplicates"
    RULES = "rules"; LIMITS = "limits"; SECURITY = "security"

class DemoExpectation(ApiModel):
    outcome: InboxEmailStatus          # final inbox status expected for the step
    rule_ids: list[str] = []           # e.g. ["R14"]
    summary: str                       # English, one line

class DemoScenarioView(ApiModel):
    scenario_id: str                   # e.g. "dup_exact"
    section: DemoSectionId
    title: str
    description: str
    channel: InboxChannel
    steps: list[DemoExpectation]       # one per step, ordered

class DemoSectionView(ApiModel):
    section: DemoSectionId
    title: str
    scenarios: list[DemoScenarioView]

class DemoCatalogView(ApiModel):
    sections: list[DemoSectionView]
    is_guardrail_enforced: bool
    is_malware_scan_enabled: bool

class DemoLaunchStatus(StrEnum):
    RUNNING = "running"; COMPLETED = "completed"; FAILED = "failed"; CANCELLED = "cancelled"

class DemoLaunchStepView(ApiModel):
    index: int
    email_id: UUID | None
    status: InboxEmailStatus | None    # None until injected
    expected: DemoExpectation
    is_as_expected: bool | None        # None until terminal

class DemoLaunchView(ApiModel):
    launch_id: UUID
    scenario_id: str
    status: DemoLaunchStatus
    steps: list[DemoLaunchStepView]
    started_at: datetime
    error: str | None = None

class DemoResetResult(ApiModel):
    deleted_rows: dict[str, int]       # table -> count
    deleted_objects: int
    seeded_bills: int
    reset_at: datetime

class KitDestinations(ApiModel):
    email_address: str | None
    whatsapp_number: str | None

# DemoScenarioView additionally has: is_self_sendable: bool, self_send_hint: str
# DemoCatalogView additionally has: destinations: KitDestinations

class DemoStatusView(ApiModel):
    is_enabled: bool
    email: str | None
```

### `backend/contracts/accountability.py`

```python
class LedgerOutcome(StrEnum):
    PAID = "paid"; ESCALATED = "escalated"; HELD = "held"
    APPROVED_BY_HUMAN = "approved_by_human"; REJECTED_BY_HUMAN = "rejected_by_human"
    DUPLICATE = "duplicate"; BLOCKED = "blocked"
    NOT_AN_INVOICE = "not_an_invoice"; MISSING_INFO = "missing_info"; ERROR = "error"

LEDGER_TAB_OUTCOMES: dict[str, frozenset[LedgerOutcome]]  # "paid" | "escalated" | "stopped"
# paid = {PAID, APPROVED_BY_HUMAN}; escalated = {ESCALATED}
# stopped = {HELD, REJECTED_BY_HUMAN, DUPLICATE, BLOCKED, NOT_AN_INVOICE, MISSING_INFO, ERROR}

class LedgerReason(ApiModel):
    rule_id: str; name: str; effect: RuleEffect; reason: str

class LedgerEntryView(ApiModel):
    entry_id: UUID                   # decision_id or inbox_email_id
    occurred_at: datetime
    outcome: LedgerOutcome
    actor: DecisionActor
    payee_id: UUID | None
    payee_name: str | None
    payee_kind: PayeeKind | None
    category: PaymentCategory | None
    amount: Decimal | None
    currency: str | None
    amount_usd: Decimal | None
    fx_usd_per_unit: Decimal | None
    fx_rate_date: date | None
    fx_source: FxSource | None
    reasons: list[LedgerReason]      # non-pass rule_results, or guardrail violations mapped to rule_id "GUARD"/"MALWARE"
    explanation: str
    note: str | None
    channel: BillSourceType | None
    subject: str | None
    bill_id: UUID | None
    run_id: UUID | None
    inbox_email_id: UUID | None
    is_seeded: bool                  # run_id is None and actor is agent

class LedgerKpis(ApiModel):
    paid_count: int; paid_usd: Decimal
    escalated_count: int; escalated_usd: Decimal
    stopped_count: int; stopped_usd: Decimal   # "money protected"
    auto_pay_rate: Decimal                    # paid by agent / bill decisions by agent, 0..1

class LedgerTimelinePoint(ApiModel):
    bucket: date                              # ISO week start (Monday)
    paid: int; escalated: int; stopped: int

class LimitUsage(ApiModel):
    scope: str                                # "global" | "category:cloud" | "payee:<uuid>"
    label: str                                # "Global", "Cloud", "Andrés Felipe Gómez"
    payee_currency: str | None
    spent_usd: Decimal
    limit_usd: Decimal | None

class ReasonCount(ApiModel):
    rule_id: str; name: str; count: int

class CurrencyTotal(ApiModel):
    currency: str; amount: Decimal; amount_usd: Decimal; count: int

class LedgerSummaryView(ApiModel):
    period: str                               # "YYYY-MM" (limits/KPIs)
    kpis: LedgerKpis
    timeline: list[LedgerTimelinePoint]       # last `months` months
    limits: list[LimitUsage]                  # payees with monthly_budget_usd + categories + global
    top_reasons: list[ReasonCount]            # top 8
    currencies: list[CurrencyTotal]           # paid only, in period

class RunListItemView(ApiModel):
    run_id: UUID
    status: RunStatus
    created_at: datetime
    duration_ms: int | None                   # updated_at - created_at when terminal
    channel: BillSourceType | None
    sender: str | None
    subject: str | None
    verdict: Verdict | None
    bill_id: UUID | None
    inbox_email_id: UUID | None
    tool_count: int                           # count of tool_finished events
    error: str | None
```

### Trace contract (`backend/contracts/payments.py`)

```python
class TraceRole(StrEnum):
    SYSTEM = "system"; HUMAN = "human"; AI = "ai"; TOOL = "tool"

class TraceToolCall(ApiModel):
    call_id: str; name: str; args: dict

class TraceMessage(ApiModel):
    index: int
    role: TraceRole
    text: str                                 # message_text(content)
    tool_calls: list[TraceToolCall] = []
    tool_call_id: str | None = None
    tool_name: str | None = None
    output_json: dict | list | None = None    # json.loads(text) for TOOL when parseable

class RunTraceView(ApiModel):
    run_id: UUID
    is_available: bool
    checkpoint_id: str | None
    messages: list[TraceMessage]
```

### Settings

```python
class FxSettings(BaseSettings):        # env_prefix="BLINKA_FX__"
    latest_url: str = "https://open.er-api.com/v6/latest/USD"
    timeout_seconds: float = 2.0
    max_stale_days: int = 7
    live_enabled: bool = True

class DemoSettings(BaseSettings):      # env_prefix="BLINKA_DEMO__"
    enabled: bool = False
    email: str = "demo@blinka.dev"
    password: SecretStr | None = None  # validator: required when enabled
    company_name: str = "Andescape Labs, Inc."
    inbox_address: str | None = None   # connected Gmail shown in the self-send kit
```

### Frontend types (`frontend/src/lib/types.ts`)

Mirror every contract above by hand, with snake_case fields and `Decimal = string`. Remove `SimulatedEmailKind`.
