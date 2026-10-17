# Composio Mail Gateway Implementation

## Overview

This is the only adapter to the Composio SDK. It handles OAuth links, connection status, new-mail triggers, webhook verification and parsing, and fetching an email's content and its PDF attachment. It exchanges only `contracts/mail_gateway.py` types with other modules.

## Files to Modify/Create

- `backend/contracts/mail_gateway.py` (new): `MailProvider`, `MailAccountStatus`, `MailboxLink`, `MailTriggerEvent`, `FetchedAttachment`, `FetchedEmail`, exactly as in `03-design.md`.
- `backend/modules/mail_gateway/__init__.py` (new): facade exporting the service and errors.
- `backend/modules/mail_gateway/errors.py` (new):
  - `MailGatewayError(Exception)`
  - `WebhookSignatureError(MailGatewayError)`
  - `MailProviderError(MailGatewayError)`, for SDK, network or tool failures
  - `MailboxAlreadyConnectedError(MailGatewayError)`
- `backend/modules/mail_gateway/gmail.py` (new): pure mappers for the Gmail payload and attachments.
- `backend/modules/mail_gateway/outlook.py` (new): pure mappers for the Outlook message and attachments.
- `backend/modules/mail_gateway/service.py` (new): `MailGatewayService`.
- `backend/clients/mail_gateway.py` (new): `MailGatewayClient`, which mirrors each service method one to one.
- `backend/scripts/bootstrap_composio.py` (new): creates the managed auth configs.

## Implementation Guidelines

### Constants (`service.py`)

```python
GMAIL_NEW_MESSAGE_TRIGGER = "GMAIL_NEW_GMAIL_MESSAGE"
OUTLOOK_NEW_MESSAGE_TRIGGER = "OUTLOOK_MESSAGE_TRIGGER"
TRIGGER_MESSAGE_EVENT = "composio.trigger.message"
TOOLKIT_PROVIDERS = {"GMAIL": MailProvider.GMAIL, "OUTLOOK": MailProvider.OUTLOOK}
ACCOUNT_STATUSES = {"ACTIVE": ACTIVE, "INITIATED": INITIATED, "FAILED": FAILED,
                    "EXPIRED": EXPIRED, "INACTIVE": EXPIRED, "REVOKED": EXPIRED}
PDF_MIME = "application/pdf"
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
```

### `MailGatewayService(settings: ComposioSettings)`

The SDK client is `Composio(api_key=settings.api_key.get_secret_value())`. Every SDK call except `parse` is wrapped as `await asyncio.to_thread(...)`. Wrap `composio.exceptions.*` and `httpx.HTTPError` as `raise MailProviderError from error`, except where a specific mapping is listed below.

| Method | Behaviour |
|---|---|
| `async link_account(user_id: UUID, provider: MailProvider, callback_url: str) -> MailboxLink` | Calls `connected_accounts.link(str(user_id), <auth_config_id for provider>, callback_url=callback_url)`. Returns `MailboxLink(connected_account_id=req.id, redirect_url=req.redirect_url)`. `ComposioMultipleConnectedAccountsError` → `MailboxAlreadyConnectedError`. |
| `async get_account_status(connected_account_id: str) -> MailAccountStatus` | `connected_accounts.get(ca_id).status`, mapped through `ACCOUNT_STATUSES`. |
| `async enable_new_mail_trigger(provider, connected_account_id) -> str` | `triggers.create(slug, connected_account_id=ca_id, trigger_config=...)`. Returns `.trigger_id`. Gmail config: `{"labelIds": "INBOX", "interval": settings.gmail_poll_interval_minutes}`. Outlook config: `{"folder_id": "inbox"}`. |
| `parse_webhook(body: bytes, headers: Mapping[str, str]) -> MailTriggerEvent \| None` | **Sync**, no I/O. An empty `webhook_secret` raises `WebhookSignatureError`. Otherwise it calls `triggers.parse(body=body, headers=dict(headers), verify_secret=secret)`, and `WebhookSignatureVerificationError` → `WebhookSignatureError`. It returns `None` when `raw_payload["type"] != TRIGGER_MESSAGE_EVENT` or the toolkit is not in `TOOLKIT_PROVIDERS`. Otherwise it builds `MailTriggerEvent(provider, connected_account_id=payload["metadata"]["connected_account"]["id"], message_id=<see below>, data=payload["payload"] or {})`. |
| `async fetch_email(event: MailTriggerEvent) -> FetchedEmail` | Dispatches to `_fetch_gmail` or `_fetch_outlook`. |

For `message_id`:
- **Gmail:** `data.get("message_id") or data["id"]`.
- **Outlook:** `data["id"]`.

### `_fetch_gmail(event)`

- Text fields come straight from the trigger payload, so there is no extra fetch:
  - `sender = data["sender"]`
  - `subject = data["subject"]`
  - `body = data["message_text"]`
  - `received_at = parse_timestamp(data["message_timestamp"])`
- The timestamp is in epoch milliseconds or ISO format. Handle both, and return `None` on failure.
- Attachments: `gmail.first_pdf_attachment(data.get("attachment_list") or [])` returns `(attachment_id, filename) | None`. Match these keys defensively:
  - `attachmentId` / `attachment_id`
  - `filename` / `name`
  - `mimeType` / `mimetype`

  An item counts as a PDF when its mime is `application/pdf` or its filename ends in `.pdf`.
- If a PDF is found, call:
  ```python
  tools.execute("GMAIL_GET_ATTACHMENT",
                {"message_id": message_id, "attachment_id": attachment_id,
                 "file_name": filename, "user_id": "me"},
                connected_account_id=ca_id, version=settings.gmail_toolkit_version)
  ```
  - A result with `successful` false → `MailProviderError`.
  - Find the file object with `gmail.find_s3url(result["data"])`. This is a recursive search for the first dict containing an `"s3url"` key.
  - Download it with `httpx.AsyncClient().get(s3url, timeout=30)`.
  - Skip the file if it is larger than `MAX_ATTACHMENT_BYTES`.
- Log `logger.info("gmail_event_shape", attachment_keys=..., data_keys=...)` once per event, so the payload can be verified live. Remove this after verification.

### `_fetch_outlook(event)`

1. Fetch the message:
   ```python
   tools.execute("OUTLOOK_GET_MESSAGE", {"message_id": msg_id, "user_id": "me"},
                 connected_account_id=ca_id, version=settings.outlook_toolkit_version)
   ```
   `outlook.to_email_fields(result["data"])` returns `sender`, `subject`, `body` and `received_at`:
   - `sender` from `from.emailAddress.address`
   - `subject`
   - `body` from `body.content`, with tags stripped via `re.sub(r"<[^>]+>", " ", ...)` and `html.unescape` when `body.contentType == "html"`
   - `received_at` from `receivedDateTime`

   Look under `data`, then `data.get("response_data", data)`, because the tool wraps the Graph response.
2. If `hasAttachments`, list them:
   ```python
   tools.execute("OUTLOOK_LIST_OUTLOOK_ATTACHMENTS",
                 {"message_id": msg_id, "response_detail": "full"}, ...)
   ```
   Items are under `data.response_data.value`. Take the first item whose `@odata.type` ends with `fileAttachment` and whose `contentType` is `application/pdf` (or whose `name` ends in `.pdf`). Decode its content with `base64.b64decode(item["contentBytes"])`.

### `scripts/bootstrap_composio.py`

Run it with `uv run python -m scripts.bootstrap_composio`. This script is orientative: check the exact list call with `help(composio.auth_configs)`.

- For each toolkit in `("gmail", "outlook")`, reuse an existing managed auth config for that toolkit (`composio.auth_configs.list(...)`). Otherwise create one:
  ```python
  composio.auth_configs.create(toolkit=slug,
                               options={"type": "use_composio_managed_auth", "name": f"Blinka {slug}"})
  ```
- Print `BLINKA_COMPOSIO__GMAIL_AUTH_CONFIG_ID=ac_...` and `BLINKA_COMPOSIO__OUTLOOK_AUTH_CONFIG_ID=ac_...`.
- Print the dev listener instructions:
  ```
  export COMPOSIO_WEBHOOK_SECRET=$(openssl rand -hex 32)   # same value in backend/.env
  composio dev triggers listen --forward http://localhost:8000/webhooks/composio
  ```

## Dependencies

- `composio==0.28.0` and `httpx` (spec 01).
- `ComposioSettings` (spec 01).

## Integration Notes

- `MailboxLink.connected_account_id` is stored by inbox at link time and later used to resolve the owner of incoming webhooks.
- `parse_webhook` is sync on both the client and the service, because it does no I/O. The inbox calls it directly.
- `FetchedEmail.attachments` contains at most one PDF.
- No other module may `import composio`.
