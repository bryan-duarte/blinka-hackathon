# Implementation Tasks

## Task Breakdown

### 1. Config & dependencies (`06-implementation/01-config-dependencies`)
- [x] `uv add "composio==0.28.0" "composio-client==2.0.0rc17"`. Move `httpx>=0.28` to the main dependencies. Run `uv lock` and `uv sync`.
- [x] Add `GuardrailsSettings`, `ComposioSettings` and `CorsSettings` to `core/config.py`. Remove `Settings.guardrails_enforce`.
- [x] Update `.env.example` with the new keys. Tell the user which keys to add to `backend/.env` (`COMPOSIO_API_KEY` is already there).
- [x] Move `ExecutionRegistry` to `core/background.py`, re-export it from `modules/payments`, and update `runner.py`'s import.

### 2. Bedrock guardrails (`06-implementation/02-guardrails-bedrock`)
- [x] `modules/guardrails/bedrock.py`: a `GuardrailBackend` Protocol and `BedrockGuardrailBackend.apply(text) -> GuardrailVerdict`.
- [x] `GuardrailsService`: chunk the text, call the backend when `enforce` is true, and map AWS errors to `GuardrailUnavailableError`.
- [x] `scripts/create_guardrail.py`: idempotent create plus version, Standard tier, profile `panoptico`. It prints the `.env` lines.
- [x] Run the script, then smoke-test with one benign string and one jailbreak string.

### 3. Composio mail gateway (`06-implementation/03-mail-gateway-composio`)
- [x] `contracts/mail_gateway.py`.
- [x] `modules/mail_gateway/`: errors, `gmail.py` and `outlook.py` mappers, and a `MailGatewayService` with `link_account`, `get_account_status`, `enable_new_mail_trigger`, `parse_webhook` and `fetch_email`.
- [x] `clients/mail_gateway.py`.
- [x] `scripts/bootstrap_composio.py`: create the managed Gmail and Outlook auth configs and print their IDs.
- [ ] Verify against one live event: the Gmail `attachment_list` keys and the `GMAIL_GET_ATTACHMENT` `s3url` location. _(Pending user: needs a real Gmail OAuth connection; the `gmail_event_shape` log line captures the keys.)_

### 4. Payments → CLP agent, TEMPORAL (`06-implementation/04-payments-clp-agent`)
- [x] Add `ClpConversion` and `InvoiceClpAnalysis` to contracts, and `analysis` to `PaymentRunStatus`.
- [x] Add the `convert_to_clp` tool with `DUMMY_CLP_RATES`. Unwire `execute_payment`. Add `ToolStrategy` to `build_payment_agent`.
- [x] Rewrite `PAYMENT_AGENT_PROMPT` and set `response_schema`. Add the Chilean rules to the invoice extraction prompt.
- [x] In the runner, read `structured_response`, store `{"summary", "analysis"}`, and raise `MissingAnalysisError` if it is absent.
- [x] Make `PaymentsService.get_run` fill `analysis`.
- [x] Add `# TEMPORAL:` comments on every repurposed spot.

### 5. Inbox module (`06-implementation/05-inbox-module`)
- [x] `contracts/inbox.py`.
- [x] `modules/inbox/models.py`: `MailboxConnection` and `InboxEmail`. Import the models in `alembic/env.py`, then autogenerate the migration and apply it.
- [x] `modules/inbox/repository.py`: connections and emails CRUD, dedupe insert, `fail_unfinished`.
- [x] `modules/inbox/samples.py`: four simulated emails.
- [x] `modules/inbox/pipeline.py`: `InboxDependencies` and `process_email`.
- [x] `modules/inbox/service.py`: connect, confirm, list connections, ingest webhook, simulate, list/get emails (with derived status), `fail_unfinished`, shutdown.
- [x] `clients/inbox.py`.
- [x] Add `get_user` to `AuthService`/`AuthClient` and a `UserMissingError`.

### 6. API wiring (`06-implementation/06-api-wiring`)
- [x] `api/routers/inbox.py` (authenticated) and `api/routers/webhooks.py` (public). Register both in `api/routers/__init__.py`.
- [x] `container.py`: build the Bedrock backend, the mail gateway and the inbox (with its own `ExecutionRegistry`), and add them to `Clients`.
- [x] `api/app.py`: CORS middleware, new exception handlers, and the inbox sweep and shutdown in `lifespan`.
- [x] Smoke test: register, connect Gmail (link + confirm), simulate all four kinds, signed webhook paths. _(Real email via CLI forward pending user OAuth.)_

### 7. Frontend inbox (`06-implementation/07-frontend-inbox`)
- [x] `src/lib/api.ts` (fetch with bearer token, 401 → `/login`) and `src/lib/types.ts`.
- [x] `/login` page (login/register toggle).
- [x] `/inbox` page: connection bar, simulate menu, email list, detail pane, 4-second polling.
- [x] `/inbox/callback` page: confirm the connection and redirect.
- [x] `/` redirects to `/inbox` or `/login`. Add `NEXT_PUBLIC_API_URL` to `frontend/.env.example`.
- [x] Use the `frontend-design` skill while building.

### Post-Implementation Quality Gate
- [x] Run a two-subagent quality pass over the change just applied:
  - [x] **Bug sweep:** launch a subagent to search the modified code for possible bugs, issues and inconsistencies (logic errors, edge cases, broken contracts, dead code, regressions). Report concrete findings as `file:line` references.
  - [x] **Polish:** launch a subagent that invokes the `codebase-change` skill and applies the polish DIRECTLY to the changed files:
    - delete unnecessary comments, but keep the `# TEMPORAL:` markers
    - make the code self-explanatory, and give every variable an obvious purpose
    - maximize readability and maintainability, and remove unnecessary complexity
    - resolve any real issues the bug sweep surfaced

## Task Order

```
1 Config ──┬──► 2 Guardrails ──┐
           ├──► 3 Mail gateway ┼──► 5 Inbox ──► 6 API wiring ──► 7 Frontend ──► Quality gate
           └──► 4 Payments CLP ┘
```
Tasks 2, 3 and 4 are independent of each other and can run in parallel.
