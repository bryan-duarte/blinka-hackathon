# WhatsApp (Kapso) Gateway Backend Implementation

## Overview

A `whatsapp_gateway` module is an httpx client for the Kapso Platform and Meta-proxy APIs, mirroring `mail_gateway`. It handles:
- creating customers, setup links and sandbox activations;
- confirming connected phone numbers;
- registering phone-number webhooks;
- verifying and parsing `whatsapp.message.received` webhooks into `WhatsAppDocumentEvent`s (accepted documents only);
- downloading the document into a `FetchedEmail`.

## Files to Modify/Create

- `backend/contracts/whatsapp_gateway.py` (new): `WhatsAppConnectionMode`, `WhatsAppDocumentEvent`, `SandboxActivation`, `KapsoSetupLink`, `KapsoPhoneNumber`, `RegisterSandboxRequest`, `WhatsAppSandboxView`, `ConfirmWhatsAppRequest` (fields in `03-design.md`).
- `backend/modules/whatsapp_gateway/__init__.py`, `errors.py`, `service.py`, `kapso.py` (new):
  - `errors.py`: `WhatsAppGatewayError` → `WhatsAppSignatureError`, `WhatsAppProviderError`, `WhatsAppPhoneInvalidError`, `WhatsAppNumberUnverifiedError`.
  - `kapso.py`: pure payload helpers (`normalize_phone`, `iter_message_payloads`, `document_event`), with no I/O.
  - `service.py`: `WhatsAppGatewayService(settings: KapsoSettings)`.
- `backend/clients/whatsapp_gateway.py` (new): `WhatsAppGatewayClient`, a one-to-one pass-through.
- `backend/core/config.py`: `KapsoSettings` (see design), nested as `Settings.kapso`.
- `backend/.env.example`: a `# Kapso (WhatsApp)` section.
- `backend/container.py`: `whatsapp_gateway = WhatsAppGatewayClient(WhatsAppGatewayService(settings.kapso))`. Inject it into `InboxDependencies` and expose it as `Clients.whatsapp_gateway`.
- `backend/api/app.py` `DOMAIN_ERROR_RESPONSES`:

  | Error | Status | detail |
  |---|---|---|
  | `WhatsAppSignatureError` | 401 | "invalid webhook signature" |
  | `WhatsAppProviderError` | 502 | "whatsapp provider unavailable" |
  | `WhatsAppPhoneInvalidError` | 422 | "invalid phone number" |
  | `WhatsAppNumberUnverifiedError` | 409 | "whatsapp number not verified" |
- `backend/scripts/bootstrap_kapso.py` (new, mirrors `scripts/bootstrap_composio.py`):
  - Lists phone numbers and finds the sandbox one (`meta_app_id is None`).
  - Prints the `BLINKA_KAPSO__SANDBOX_PHONE_NUMBER_ID` and `BLINKA_KAPSO__SANDBOX_DISPLAY_NUMBER` lines.
  - Registers the message webhook on it, idempotently: skip if a webhook with the same url exists.
  - Prints the ngrok hint `ngrok http 8000`, plus the webhook URL to set.

## Implementation Guidelines

### Spike first (task 0)

Before building the sandbox and media paths, run one manual check with `curl` and the API key:
1. `POST https://api.kapso.ai/api/v1/sandbox_sessions` (legacy, unconfirmed): note the request body and response.
2. Send a PDF to the sandbox number from a registered tester, with a webhook pointed at `https://webhook.site/...`, and confirm:
   - a `type=document` message arrives;
   - `message.kapso.media_url` is present;
   - `GET media_url` with `X-API-Key` returns the bytes.
3. Record the findings in this spec's "Spike results" section, and adjust `create_sandbox_session` and `download_document` to match.

### Service methods (`WhatsAppGatewayService`)

```python
# orientative
KAPSO_PLATFORM = "/platform/v1"
KAPSO_META = "/meta/whatsapp/v24.0"
MESSAGE_RECEIVED_EVENT = "whatsapp.message.received"
ACCEPTED_DIRECTION = "inbound"
MAX_DOCUMENT_BYTES = 10 * 1024 * 1024   # same cap as mail attachments

async def ensure_customer(self, owner_id: UUID, name: str) -> str
    # POST /platform/v1/customers {"customer":{"name": name, "external_customer_id": str(owner_id)}} → data.id
    # The caller stores the result in mailbox_connections.external_ref and reuses it when present.

async def create_setup_link(self, customer_id: str) -> KapsoSetupLink
    # POST /platform/v1/customers/{id}/setup_links {"setup_link":{
    #   "success_redirect_url": callback_url, "failure_redirect_url": callback_url,
    #   "allowed_connection_types": ["coexistence","dedicated"], "language": "es"}}

async def get_phone_number(self, customer_id: str, phone_number_id: str) -> KapsoPhoneNumber
    # GET /platform/v1/whatsapp/phone_numbers?customer_id=..&phone_number_id=..; match both ids, else WhatsAppNumberUnverifiedError

async def register_message_webhook(self, phone_number_id: str) -> str
    # POST /platform/v1/whatsapp/phone_numbers/{id}/webhooks {"whatsapp_webhook":{
    #   "url": webhook_url, "secret_key": webhook_secret, "events": [MESSAGE_RECEIVED_EVENT],
    #   "kind": "kapso", "payload_version": "v2", "active": true, "buffer_enabled": false}} → data.id

async def create_sandbox_session(self, phone_e164: str) -> SandboxActivation | None
    # per spike; any httpx.HTTPError / non-2xx / missing fields → log "kapso_sandbox_session_unavailable" and return None

def parse_webhook(self, body: bytes, headers: Mapping[str, str]) -> list[WhatsAppDocumentEvent]
    # 1. secret empty → WhatsAppSignatureError
    # 2. hmac.compare_digest(hmac.new(secret, body, sha256).hexdigest(), headers["x-webhook-signature"]) else WhatsAppSignatureError
    # 3. headers["x-webhook-event"] != MESSAGE_RECEIVED_EVENT → []
    # 4. payloads = kapso.iter_message_payloads(json) (handles batch {"data":[...]} and single)
    # 5. for each: kapso.document_event(payload) → event | None (filters type=="document", kapso.direction=="inbound",
    #    filename extension in EVIDENCE_MIME_BY_EXTENSION). Log "whatsapp_message_ignored" (debug) with the type for the rest.

async def fetch_message(self, event: WhatsAppDocumentEvent) -> FetchedEmail
    # attachment = await self._download(event); return FetchedEmail(
    #   sender=f"{event.contact_name} <{event.sender_phone}>" if event.contact_name else event.sender_phone,
    #   subject=event.filename, body=event.caption, received_at=event.received_at, attachments=[attachment])

async def _download(self, event) -> FetchedAttachment
    # A: media_url present → GET with X-API-Key only when host endswith "kapso.ai"
    # B: else GET {base}{KAPSO_META}/{media_id}?phone_number_id={id} → data["download_url"] → GET (no auth)
    # reject > MAX_DOCUMENT_BYTES → WhatsAppProviderError("document too large"), mime from event.mime
```

- All HTTP goes through one private `_request(method, path, json=None, params=None) -> dict`. It sets `X-API-Key`, uses `timeout=30`, unwraps `{"data": ...}`, and maps `httpx.HTTPError` / 4xx / 5xx to `WhatsAppProviderError` (`raise ... from error`).
- `kapso.normalize_phone(raw)` keeps a leading `+` and strips spaces, dashes and parentheses. It raises `WhatsAppPhoneInvalidError` unless the result matches `^\+[1-9]\d{7,14}$`. If the input has no `+`, add it.
- `kapso.document_event` reads these fields:

  | Field | Path in the payload |
  |---|---|
  | `message_id` | `message.id` |
  | `sender_phone` | `conversation.phone_number`, normalized |
  | `contact_name` | `conversation.kapso.contact_name` |
  | `phone_number_id` | `phone_number_id` (root), or `conversation.phone_number_id` |
  | `filename` | `message.document.filename`, or `message.kapso.media_data.filename` |
  | `caption` | `message.document.caption`, or `message.kapso.message_type_data.caption`, or `""` |
  | `media_url` | `message.kapso.media_url`, or `media_data.url` |
  | `media_id` | `message.document.id` |
  | `received_at` | `message.timestamp` (unix seconds → UTC datetime) |

  `mime` comes from `EVIDENCE_MIME_BY_EXTENSION[extension]`.

### Self-check

Add a small assert script or test over the pure helpers in `kapso.py`:
- signature ok vs tampered;
- batch vs single payloads;
- a document `.pdf` is accepted, while `image` and `.docx` are ignored;
- `normalize_phone("+56 9 1234-5678") == "+56912345678"`.

## Dependencies

- `httpx` (already present), `contracts.files.EVIDENCE_MIME_BY_EXTENSION`, and `contracts.mail_gateway.FetchedEmail` / `FetchedAttachment`.
- Kapso project API key and webhook secret (the user generates the secret, e.g. `openssl rand -hex 32`).

## Integration Notes

- **Consumed by module 06** (`InboxService`, `pipeline._resolve_email`): `parse_webhook` → `list[WhatsAppDocumentEvent]`; `fetch_message(event)` → `FetchedEmail`.
- **Routing keys:** `event.phone_number_id` (own number) and `event.sender_phone` (sandbox).
- **`external_message_id`** = `event.message_id` (the wamid), so duplicate deliveries are no-ops through the existing unique constraint.

## Spike results

Run on 2026-10-17 against the project's Kapso API key.

- `GET /platform/v1/whatsapp/phone_numbers` lists the shared sandbox number with `kind: "sandbox"`, `phone_number_id: 597907523413541` and `display_phone_number: null`. The display number has to be copied from the dashboard into `BLINKA_KAPSO__SANDBOX_DISPLAY_NUMBER`.
- `POST /api/v1/sandbox_sessions`, `/platform/v1/sandbox_sessions` and `/platform/v1/whatsapp/sandbox` all return 404. The docs describe sandbox sessions only in the dashboard (WhatsApp → Sandbox → Add Test Number), with a 6-character code that expires after 15 minutes. **Decision:** no sandbox-session call; `WhatsAppSandboxView` carries no `activation` field and the UI always shows the manual instructions.
- Media: the documented path is `GET /meta/whatsapp/v24.0/{media_id}?phone_number_id=…` (X-API-Key) → `download_url` (no auth, ~4 min). `_download` prefers it and falls back to `message.kapso.media_url` with the key only for `*.kapso.ai` hosts.
- Inbound `document` delivery on the sandbox is not documented; not verified with a real phone (needs a public webhook URL). A signed synthetic webhook was verified end to end against the local API.
