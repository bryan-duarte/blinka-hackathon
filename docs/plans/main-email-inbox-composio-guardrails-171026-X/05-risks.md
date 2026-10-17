# Risks & Mitigations

## Technical Risks

| Risk | Impact | Mitigation |
|---|---|---|
| `composio 0.28.0` pins the pre-release `composio-client==2.0.0rc17`. `--prerelease=allow` pulls a broken `httpx 1.0.dev6`. | high | Pin both packages explicitly and never pass `--prerelease=allow`. Check `uv.lock` shows `httpx 0.28.x`. |
| The Composio SDK is sync. Calling it on the event loop blocks every request. | high | Every call in `MailGatewayService` goes through `asyncio.to_thread`. Only `triggers.parse` runs inline, because it does no I/O. |
| `connected_accounts.initiate()` and `toolkits.authorize()` hit the endpoint that was retired on 2026-07-03 for managed auth. | high | Use only `connected_accounts.link()`. |
| The Gmail `attachment_list` item keys and the location of `GMAIL_GET_ATTACHMENT`'s `s3url` inside `data` are undocumented. | med | Map them defensively (`attachmentId`/`attachment_id`, `filename`/`name`, `mimeType`/`mimetype`). Log the keys on the first live event. Verification is an explicit task. |
| Whether PROMPT_ATTACK fires on an unqualified `ApplyGuardrail` block is medium confidence. | med | Send `qualifiers=["guard_content"]`. The smoke test with the `prompt_injection` sample must come back `blocked`. |
| The Standard tier needs `crossRegionConfig` and IAM on the `us.guardrail.v1:0` profile. The `panoptico` user's permissions are unverified for create/apply. | med | The bootstrap script surfaces `AccessDeniedException` clearly. If needed, add `bedrock:CreateGuardrail`, `CreateGuardrailVersion`, `ApplyGuardrail` and `GetGuardrail` on the guardrail and profile ARNs. |
| An ANONYMIZE or detect-only policy returns `GUARDRAIL_INTERVENED` without blocking anything. | med | The verdict counts only assessments with `action == "BLOCKED"`. The bootstrap guardrail has no PII policy. |
| Background tasks live only in memory. A restart loses in-flight emails and runs. | low | Startup sweeps mark them `error` / `failed`. Acceptable for a test layer. |
| `GET /inbox/emails` makes one `payments.get_run` call per analyzing email (N+1). | low | Cap the list at 50 emails. Revisit with a batch query if the inbox grows. |
| The chat flow's `initiate_payments` now produces a CLP analysis instead of executing a payment. | low | This is intended and marked `# TEMPORAL`. Restoring it means re-adding `execute_payment` to the toolset. |
| The Docker backend container has no `~/.aws` profile, so guardrails fail there. | low | Run the backend via `pnpm dev` for this layer. Mounting `~/.aws` read-only is a follow-up. |

## Integration Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Renaming `BLINKA_GUARDRAILS_ENFORCE` to `BLINKA_GUARDRAILS__ENFORCE` silently resets enforcement to `False`. | med | Update `.env.example` and tell the user to update `backend/.env`. Log `guardrails_configured enforce=...` at startup. |
| `COMPOSIO_WEBHOOK_SECRET` is empty, or differs between the CLI and the backend, so every event gets a 401. | med | Fail closed and log `composio_webhook_rejected` with the reason. Document `export COMPOSIO_WEBHOOK_SECRET=$(openssl rand -hex 32)` for both processes. |
| Composio's callback query params (`connected_account_id`) are not proof of ownership. | med | `confirm_connection` only accepts a `connected_account_id` whose row belongs to the current user. |
| The extraction LLM invents invoice data for non-invoice text. | med | The agent's `InvoiceClpAnalysis.is_invoice=false` gives a second chance. The view maps it to `no_invoice`. |
| The new migration must chain after `ef10b9a6dbf3`. | low | Autogenerate from the `product` section only. |

## Edge Cases Identified

- **Duplicate webhook delivery or retries:** the unique `(provider, external_message_id)` constraint plus `ON CONFLICT DO NOTHING` means a duplicate spawns nothing.
- **Webhook for an unknown `connected_account_id`** (e.g. a connection deleted locally): log it, acknowledge with 202, process nothing.
- **Non-message Composio events** (`composio.connected_account.expired`): log and acknowledge only.
- **Connecting a provider that is already ACTIVE:** `ComposioMultipleConnectedAccountsError` maps to `MailboxAlreadyConnectedError`, which returns 409. The UI shows "already connected".
- **The OAuth callback arrives while the status is still INITIATED:** the callback page retries `confirm` up to 10 times, 1 second apart.
- **Empty subject and body with no PDF:** the body file is still created, extraction fails, and the email ends as `no_invoice`.
- **Multiple PDFs:** only the first is used. Attachments larger than 10 MB (`MAX_ATTACHMENT_BYTES`) are skipped.
- **Outlook HTML bodies:** tags are stripped with the stdlib (`html.unescape` plus a tag regex) before the text is guarded and stored.
- **Guard text longer than one call allows:** it is split into chunks of 25,000 characters. The PDF preview is already capped at 20,000 characters by `files/extract.py`.
- **Unknown currency in `convert_to_clp`:** the tool returns `{"error": "unsupported currency"}`. The agent reports it in `summary` and leaves `amount_clp=null`, and the email stays `analyzed`.
- **Guardrails disabled (`ENFORCE=false`):** the `prompt_injection` sample passes. The UI shows it analyzed, which is expected but should be mentioned in the demo.
