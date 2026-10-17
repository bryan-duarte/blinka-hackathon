# API Wiring Implementation

## Overview

This exposes the inbox and webhook routes, wires the new modules in the composition root, and adds CORS, error mappings and the inbox lifecycle hooks.

## Files to Modify/Create

- `backend/api/routers/inbox.py` (new): `inbox_router = APIRouter(prefix="/inbox", tags=["inbox"])`.
- `backend/api/routers/webhooks.py` (new): `webhooks_router = APIRouter(prefix="/webhooks", tags=["webhooks"])`.
- `backend/api/routers/__init__.py`: import both and include them.
- `backend/container.py`: add `mail_gateway` and `inbox` to `Clients`, and add new builds.
- `backend/api/app.py`: in `create_app`, add CORS and the new handlers. In `lifespan`, add the inbox sweep and shutdown.

## Implementation Guidelines

These snippets are orientative.

### `api/routers/inbox.py`

| Route | Request | Response | Calls |
|---|---|---|---|
| `POST /inbox/connections` (201) | `ConnectMailboxRequest` | `MailboxConnectStarted` | `clients.inbox.start_connection(user, request.provider)` |
| `POST /inbox/connections/confirm` | `ConfirmMailboxRequest` | `MailboxConnectionView` | `clients.inbox.confirm_connection(user, request.connected_account_id)` |
| `GET /inbox/connections` | none | `list[MailboxConnectionView]` | `clients.inbox.list_connections(user)` |
| `GET /inbox/emails` | none | `list[InboxEmailView]` | `clients.inbox.list_emails(user)` |
| `GET /inbox/emails/{email_id}` | path `UUID` | `InboxEmailDetail` | `clients.inbox.get_email(user, email_id)` |
| `POST /inbox/simulate` (202) | `SimulateEmailRequest` | `InboxEmailView` | `clients.inbox.simulate(user, request.kind)` |

Handlers follow `api/routers/payments.py`, using `CurrentUserDep`, `ClientsDep`, `response_model=` and a matching return annotation. There are no guardrail calls here; the pipeline does them.

### `api/routers/webhooks.py`

```python
@webhooks_router.post("/composio", status_code=status.HTTP_202_ACCEPTED)
async def composio_webhook(request: Request, clients: ClientsDep) -> dict:
    await clients.inbox.ingest_webhook(await request.body(), request.headers)
    return {"status": "accepted"}
```

The body must be the raw bytes, because the HMAC is computed over them. Do not declare a pydantic body parameter.

### `api/routers/__init__.py`

```python
api_router.include_router(webhooks.webhooks_router)
api_router.include_router(inbox.inbox_router, dependencies=[Depends(get_current_user)])
```

### `container.py`

```python
guardrails_settings = settings.guardrails
guardrails = GuardrailsClient(GuardrailsService(
    guardrails_settings,
    BedrockGuardrailBackend(guardrails_settings.guardrail_id, guardrails_settings.guardrail_version,
                            guardrails_settings.aws_profile, guardrails_settings.aws_region),
))
mail_gateway = MailGatewayClient(MailGatewayService(settings.composio))
...
# after payments
inbox_repository = InboxRepository(product_sessionmaker)
inbox_dependencies = InboxDependencies(repository=inbox_repository, files=files,
                                       guardrails=guardrails, payments=payments,
                                       mail_gateway=mail_gateway)
inbox = InboxClient(InboxService(inbox_repository, ExecutionRegistry(), inbox_dependencies,
                                 auth=auth, callback_url=settings.composio.callback_url))
```

Add `mail_gateway: MailGatewayClient` and `inbox: InboxClient` to the `Clients` dataclass and to the `Clients(...)` return.

### `api/app.py`

- In `lifespan`:
  - after `clients.payments.fail_unfinished(...)`: `await clients.inbox.fail_unfinished(RESTART_INTERRUPTION_REASON)`
  - in `finally`, before `payments.shutdown_runs()`: `await clients.inbox.shutdown()`
  - log `logger.info("guardrails_configured", enforce=settings.guardrails.enforce)`
- In `create_app`:

  ```python
  app.add_middleware(CORSMiddleware, allow_origins=CorsSettings().allow_origins,
                     allow_credentials=False, allow_methods=["*"], allow_headers=["*"])
  ```

  `allow_credentials=False` is enough because a bearer header is not a credentialed cookie.

New handlers follow the existing `_reject_*` style:

| Error | Status | `detail` |
|---|---|---|
| `GuardrailUnavailableError` | 503 | `"guardrails unavailable"` |
| `WebhookSignatureError` | 401 | `"invalid webhook signature"` |
| `MailboxConnectionMissingError` | 404 | `"mailbox connection not found"` |
| `EmailMissingError` | 404 | `"email not found"` |
| `MailboxAlreadyConnectedError` | 409 | `"mailbox already connected"` |
| `MailProviderError` | 502 | `"mail provider unavailable"` |

## Dependencies

Specs 01–05.

## Integration Notes

### Manual end-to-end smoke test, in order

1. `docker compose up -d postgres-product postgres-agent postgres-payments minio`
2. `cd backend && uv run alembic -n product upgrade head && pnpm dev` (from the repo root)
3. In a separate shell, with the same `COMPOSIO_WEBHOOK_SECRET` exported: `composio dev triggers listen --forward http://localhost:8000/webhooks/composio`
4. Register, then use `POST /inbox/simulate` for each kind. Expected results:
   - `invoice_usd`: `analyzed`, `amount_clp` 114000
   - `invoice_clp`: `analyzed`, 119000
   - `prompt_injection`: `blocked` with `content.prompt_attack`
   - `plain`: `no_invoice`
5. Connect Outlook, send yourself a PDF invoice, and check that it appears within seconds.
