# Realtime Backend Implementation

## Overview

A `realtime` module publishes `RealtimeEvent`s to AppSync Events over SigV4 HTTP. Two domain choke points use it:
- `RunEventRecorder` (payments): persists run events, then publishes them.
- `InboxNotifier` (inbox): publishes item status changes.

Each tool event gets a friendly Spanish message, picked at random from a per-tool catalog.

## Files to Modify/Create

- `backend/contracts/realtime.py` (new): `RealtimeEventType`, `RealtimeEvent` (see `03-design.md`).
- `backend/modules/realtime/__init__.py` (new): exports `RealtimeService`, `AppSyncEventsBackend`, `NullRealtimeBackend` and `RealtimeError`.
- `backend/modules/realtime/errors.py` (new): `RealtimeError(Exception)`, `RealtimePublishError(RealtimeError)`.
- `backend/modules/realtime/appsync.py` (new): `AppSyncEventsBackend(settings: RealtimeSettings)` with `async publish(channel: str, events: list[str]) -> None`. Also `NullRealtimeBackend`, whose `publish` is a no-op.
- `backend/modules/realtime/service.py` (new): `RealtimeService(backend: RealtimeBackend, namespace: str)`:
  - `channel_for(owner_id: UUID) -> str` returns `f"/{namespace}/{owner_id}"`.
  - `async publish(owner_id: UUID, events: Sequence[RealtimeEvent]) -> None` chunks the events by 5 and never raises.
- `backend/clients/realtime.py` (new): `RealtimeClient`, a pass-through for `publish`.
- `backend/core/config.py`: `RealtimeSettings` (see design), nested as `Settings.realtime`.
- `backend/.env.example`: a `# Realtime (AppSync Events)` section.
- `backend/container.py`:
  - Build the backend: `AppSyncEventsBackend(settings.realtime)` if `settings.realtime.enabled and settings.realtime.http_domain`, otherwise `NullRealtimeBackend()`.
  - Wire it as `realtime = RealtimeClient(RealtimeService(backend, settings.realtime.namespace))`.
  - Pass it into `PaymentRunDependencies` and `InboxDependencies`, and expose it as `Clients.realtime`.
- `backend/modules/payments/events.py` (new): `RunEventRecorder`, `ThinkingBuffer`.
- `backend/modules/payments/phrases.py` (new): `TOOL_PHRASES`, `STEP_PHRASES`, `pick_phrase(key: str, phase: Literal["start","finish"]) -> str`.
- `backend/modules/payments/repository.py`: `insert_event(...) -> PaymentRunEvent` returns the inserted row (`.returning(AgentRunEvent)`). `list_events` includes `id`. `RUN_EVENT_LIST_LIMIT = 300`.
- `backend/contracts/payments.py`: `PaymentRunEvent.id: int`.
- `backend/modules/inbox/notifier.py` (new): `InboxNotifier(realtime: RealtimeClient)` with `async item_changed(owner_id: UUID, item_id: UUID, status: InboxEmailStatus, run_id: UUID | None = None) -> None`.
- `backend/modules/inbox/pipeline.py`: `InboxDependencies.notifier: InboxNotifier`. After every status mutation (`set_status` PROCESSING, `mark_blocked`, `mark_duplicate`, `mark_analyzing`, and both error paths in `process_email`), call `await dependencies.notifier.item_changed(owner.user_id, email_id, <status>, run_id)`.
- `backend/modules/inbox/service.py`: after `insert_email` in `ingest_webhook`, `ingest_whatsapp_webhook` and `simulate`, call `notifier.item_changed(..., InboxEmailStatus.RECEIVED)`.

## Implementation Guidelines

### AppSync publish (SigV4)

```python
# orientative — botocore 1.40.61, aioboto3 15.5.0, httpx
class AppSyncEventsBackend:
    def __init__(self, settings: RealtimeSettings) -> None:
        self._url = f"https://{settings.http_domain}/event"
        self._host = settings.http_domain
        self._region = settings.region
        self._session = aioboto3.Session(profile_name=settings.aws_profile or None, region_name=settings.region)

    async def publish(self, channel: str, events: list[str]) -> None:
        body = json.dumps({"channel": channel, "events": events})
        credentials = await self._session.get_credentials()          # default chain → instance role later
        frozen = await credentials.get_frozen_credentials()
        request = AWSRequest(method="POST", url=self._url, data=body,
                             headers={"content-type": "application/json", "host": self._host})
        SigV4Auth(frozen, "appsync", self._region).add_auth(request)
        try:
            async with httpx.AsyncClient(timeout=PUBLISH_TIMEOUT_S) as client:
                response = await client.post(self._url, content=body, headers=dict(request.headers))
                response.raise_for_status()
        except httpx.HTTPError as error:
            raise RealtimePublishError from error
```

- `PUBLISH_TIMEOUT_S = 5`. Sign the exact bytes that are sent.
- `RealtimeService.publish` serializes each event with `event.model_dump_json()`, chunks the list by `MAX_EVENTS_PER_PUBLISH = 5`, and catches `RealtimeError` plus any other exception. It logs `realtime_publish_failed` (with `owner_id` and `count`) and returns. Realtime must never break the pipeline.
- A response body with a non-empty `failed` list is logged as `realtime_publish_partial`.

### RunEventRecorder (`modules/payments/events.py`)

```python
# orientative
class RunEventRecorder:
    def __init__(self, repository: RunsRepository, realtime: "RealtimeClient", owner_id: UUID, run_id: UUID) -> None: ...
    def bind_item(self, item_id: UUID | None) -> None: ...        # inbox_email_id from the bill source

    async def step(self, step: str, payload: dict | None = None) -> None:
        message = pick_step_phrase(step)                            # may be None for steps without copy
        stored = await self._repository.insert_event(self._run_id, step, {**(payload or {}), **({"message": message} if message else {})})
        await self._publish(RealtimeEventType.RUN_STEP, stored, message)

    async def tool_started(self, tool: str, call_id: str) -> None:
        message = pick_phrase(tool, "start")
        stored = await self._repository.insert_event(self._run_id, TOOL_STARTED_STEP, {"tool": tool, "call_id": call_id, "message": message})
        await self._publish(RealtimeEventType.AGENT_TOOL, stored, message)

    async def tool_finished(self, tool: str, call_id: str, output: object, duration_ms: int) -> None: ...
        # ok = not (isinstance(output, ToolMessage) and output.status == "error") and '"error"' not in summary
        # summary = truncate(message_text(output.content), TOOL_SUMMARY_MAX_CHARS=280)

    async def todos(self, todos: list[dict]) -> None: ...            # step "todos_updated", type AGENT_TODOS
    async def agent_summary(self, text: str) -> None: ...            # step "agent_summary", type RUN_STEP
    async def thinking(self, delta: str) -> None: ...                # publish only: type AGENT_THINKING, step "thinking", payload {"text": delta}, sequence=None
```

- `_publish` builds `RealtimeEvent(type, item_id=self._item_id, run_id=self._run_id, step=stored.step, payload=stored.payload, message=message, sequence=stored.id, created_at=stored.created_at)`.
- The step-name constants `TOOL_STARTED_STEP`, `TOOL_FINISHED_STEP`, `TODOS_UPDATED_STEP` and `AGENT_SUMMARY_STEP` live in `events.py`. `runner.py` imports them alongside its existing constants.

### ThinkingBuffer

- `add(text)` appends to the buffer. If `monotonic() - last_flush >= thinking_flush_ms/1000` and the buffer is not empty, it calls `flush()`.
- `flush()` sends `recorder.thinking(buffer)`, then clears the buffer.
- Deliberate simplification: there is no background timer. The buffer flushes on the next chunk or at a tool boundary or the end of the stream. If a stalled stream ever leaves text unflushed for more than 1 s, add a timer.

### Phrase catalog (`modules/payments/phrases.py`)

These are legible Spanish messages, 3–5 per tool and phase. Example shape:

```python
TOOL_PHRASES: dict[str, dict[str, tuple[str, ...]]] = {
    "classify_document": {
        "start": ("Leyendo el documento para entender si es una factura…",
                  "Clasificando la factura: ¿cobro, cotización o nota de crédito?",
                  "Revisando qué tipo de documento llegó…"),
        "finish": ("Listo, ya sé qué tipo de documento es.", "Documento clasificado."),
    },
    "extract_invoice": {"start": ("Sacando monto, moneda y beneficiario del documento…", "Extrayendo los datos clave de la factura…", "Leyendo número de factura y fecha de vencimiento…"), "finish": (...)},
    "register_bill": {"start": ("Buscando al beneficiario en la lista permitida…", "Revisando si esta factura ya había llegado antes…"), "finish": (...)},
    "evaluate_rules": {"start": ("Comparando contra las reglas de pago de la empresa…", "Revisando límites, presupuesto y beneficiarios…"), "finish": (...)},
    "run_checker": {"start": ("Haciendo una segunda revisión antes de pagar…", "Verificando que todo cuadre con lo acordado…"), "finish": (...)},
    "settle_decision": {"start": ("Registrando la decisión y su explicación…", "Dejando constancia de por qué se decidió así…"), "finish": (...)},
}
STEP_PHRASES: dict[str, tuple[str, ...]] = {"started": ("El agente empezó a trabajar en esta factura.",), "completed": (...), "failed": (...), ...}

def pick_phrase(key: str, phase: Literal["start", "finish"]) -> str:
    return random.choice(TOOL_PHRASES[key][phase])
```

UI copy rule: no em-dashes. Use plain ellipsis "…" only for in-progress messages.

### Inbox notifier

`item_changed` publishes `RealtimeEvent(type=INBOX_ITEM, item_id=item_id, run_id=run_id, step=status, payload={"status": status}, created_at=now)`. Nothing is persisted, because the inbox row itself is the state.

## Dependencies

- Module 04 (Terraform outputs): `http_domain`, plus the IAM `appsync:EventPublish` policy for the current IAM user.
- Used by module 02 (`RunEventRecorder`, `ThinkingBuffer`) and modules 05/06 (`InboxNotifier`).

## Integration Notes

- **Wire contract consumed by the frontend (module 07).** Each AppSync message `event` is exactly `RealtimeEvent.model_dump(mode="json")`, with UUIDs and datetimes as strings.
- **Channel.** `/inbox/{owner_id}`. `namespace` must match the Terraform `aws_appsync_channel_namespace.name = "inbox"`.
- **Ordering.** Ordering is best effort. Persisted events carry `sequence` (`agent_run_events.id`), so the frontend dedupes and sorts by it. `agent.thinking` events have `sequence=None` and are only appended live.
- **Self-check.** Add a small assert-based check that `RealtimeService.publish` splits 12 events into chunks of 5, 5 and 2, and that a raising backend does not propagate. Use a fake backend.
