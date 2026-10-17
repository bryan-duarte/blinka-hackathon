# User Preferences & Decisions

## 👤 Configuration Preferences

- **Context Level**: Moderado
- **Participation Level**: Equilibrado
- **Detail Level**: Neutral. Snippets show direction only; the implementer decides the final code.

## 💬 Q&A and Rationale

### 🏷️ Composio / mailbox connection
**Q:** Which providers?
**A:** Gmail + Outlook.
**Decision:** Support both toolkits from the start.
- Gmail uses the polling trigger `GMAIL_NEW_GMAIL_MESSAGE`.
- Outlook uses the realtime trigger `OUTLOOK_MESSAGE_TRIGGER`. Its payload carries only the message id, so content is fetched with `OUTLOOK_GET_MESSAGE`.

**Rejected:** Gmail-only, which would postpone Outlook while the abstraction stays the same.

**Q:** How does the user log into the app?
**A:** The existing JWT login plus a Connect button.
**Decision:** Reuse `/auth/register` and `/auth/login`. The Blinka `users.id` is used as the Composio `user_id`. The Connect button calls `connected_accounts.link()` and redirects the browser to `redirect_url`.
**Rejected:** A single demo user with no login.

**Q:** How do events reach the local backend?
**A:** The Composio CLI forward.
**Decision:** In dev, run `composio dev triggers listen --forward http://localhost:8000/webhooks/composio`. The same handler and the same signature check are used in dev and prod.
**Rejected:** ngrok, because the subscription is project-wide. In-process `subscribe()`, because it is unsigned and takes a different code path.

**Q:** Gmail's managed auth polls only every 15 minutes. How do we test?
**A:** Managed auth plus a simulate button.
**Decision:** Keep Composio-managed auth configs and add `POST /inbox/simulate` with canned samples (`invoice_usd`, `invoice_clp`, `prompt_injection`, `plain`). The samples go through the same pipeline, skipping only the provider fetch.
**Rejected:** An own Google OAuth app, which needs too much setup for now.

**Note from the user:** `COMPOSIO_API_KEY` is already set in `backend/.env`. Read it through `validation_alias="COMPOSIO_API_KEY"` and do not rename it.

### 🏷️ Guardrails (Bedrock)
**Q:** How is the guardrail resource created?
**A:** A bootstrap script in the repo, using the `panoptico` AWS user.
**Decision:** `backend/scripts/create_guardrail.py` creates the guardrail and its version idempotently, using AWS profile `panoptico` (region `us-east-1`, verified to have Bedrock access). It prints the `.env` lines. At runtime, `aioboto3.Session(profile_name=settings.guardrails.aws_profile)` is used.
**Rejected:** Creating it manually in the AWS console.

**Q:** Which tier?
**A:** Standard.
**Decision:** Set `tierConfig.tierName="STANDARD"` and `crossRegionConfig.guardrailProfileIdentifier="us.guardrail.v1:0"`. Standard is multilingual, which matters for Spanish emails.
**Rejected:** Classic, which has lower accuracy.

**Q:** What happens to a blocked email?
**A:** It is shown as blocked in the inbox.
**Decision:** Persist `status=blocked` with a `violations` JSONB column, and start no agent run.
**Rejected:** Dropping blocked emails silently.

**Q:** Which text is guarded?
**A:** Subject, body and PDF text.
**Decision:** The guard text is `subject + body + FilesClient.get_context(pdf file)`. It is sent in chunks of 25,000 characters.
**Rejected:** Subject and body only.

### 🏷️ Agent
**Q:** Which emails start the agent?
**A:** All emails that pass the guardrail.
**Decision:** Every allowed email starts a payment run. A non-invoice ends as `no_invoice` in either of two ways:
- `InvoiceParseError`, i.e. the existing `invoice_parse_failed` step; or
- the agent returns `InvoiceClpAnalysis.is_invoice=false`.

**Rejected:** A triage gate, which adds a second LLM call. A trigger-level attachment filter, which misses invoices that are in the body.

**Q:** Where can the invoice be?
**A:** In a PDF attachment or in the body.
**Decision:** The first PDF attachment is uploaded through `FilesClient.upload`. If there is no PDF, the body is uploaded as `email-<id>.txt` (`text/plain`), which the invoice ingestor already decodes. Either way, the existing `file_id`-based payments path is reused unchanged.

**Q:** Where do CLP rates come from?
**A:** Static dummy rates.
**Decision:** The `convert_to_clp` tool uses `DUMMY_CLP_RATES = {"CLP": 1, "USD": 950, "EUR": 1030, "CLF": 39500}`.
**Rejected:** The mindicador.cl API.

**Q:** How does the CLP agent relate to the payment agent?
**A:** Repurpose the payment agent, and mark it with a "temporal" comment because it is only for testing the pipeline.
**Decision:**
- Rewrite `PAYMENT_AGENT_PROMPT`.
- Replace `execute_payment` in the toolset with `convert_to_clp`. `execute_payment` stays defined but is not wired.
- Add `response_format=ToolStrategy(InvoiceClpAnalysis)`.
- Every repurposed spot gets a `# TEMPORAL: ...` comment. This is the only exception to the repo's no-comments rule.
- The chat flow (`initiate_payments`) inherits the new behaviour.

**Rejected:** A separate analysis agent.

### 🏷️ Frontend
**Q:** How does the UI get live updates?
**A:** Polling.
**Decision:** Poll `GET /inbox/emails` every 4 seconds while any email is `received`, `processing` or `analyzing`.

**Q:** How does the frontend reach the API?
**A:** CORS and a direct URL.
**Decision:** Add `CORSMiddleware` with `CorsSettings.allow_origins` (default `["http://localhost:3000"]`). The frontend uses `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`).
**Rejected:** A Next.js rewrites proxy.

### 🏷️ Agent-decided (not asked)
- **Module split:**
  - `modules/mail_gateway` is the only place that imports `composio`. It is sync-only, so every call is wrapped in `asyncio.to_thread`.
  - `modules/inbox` owns the tables, the pipeline and the samples.
- **Background work:** `ExecutionRegistry` moves from `modules/payments/runner.py` to `core/background.py`. Inbox and payments each get their own instance. `modules/payments/__init__.py` keeps re-exporting it.
- **Owner resolution on the webhook:** `mailbox_connections.connected_account_id` → `owner_id` → a new `AuthClient.get_user(user_id) -> CurrentUser`.
- **Dedupe:** a unique `(provider, external_message_id)` constraint, with `INSERT ... ON CONFLICT DO NOTHING`. A duplicate webhook starts nothing.
- **Fail closed:**
  - When `COMPOSIO_WEBHOOK_SECRET` is empty, every webhook is rejected with 401.
  - When guardrails are unavailable, the email goes to `error` and no run starts.
- **Guard verdict:** computed from assessments with `action == "BLOCKED"` only, not from `GUARDRAIL_INTERVENED`. That way ANONYMIZE or detect-only policies never block an email. The bootstrap guardrail has no PII policy, because invoices legitimately contain emails and tax IDs.
- **Restart:** a startup sweep marks inbox emails still `received`/`processing` as `error` with "interrupted by restart". This mirrors `payments.fail_unfinished`.
- **Inbox result source:** the inbox does not copy agent output. For `analyzing` emails it reads `PaymentsClient.get_run()`. `PaymentRunStatus` gains `analysis: InvoiceClpAnalysis | None`. The list is capped at the 50 latest emails.
- **Settings:** the flat `Settings.guardrails_enforce` is replaced by the nested `GuardrailsSettings`, so the env var is now `BLINKA_GUARDRAILS__ENFORCE`.
- **Invoice extraction prompt:** gains rules for Chilean invoices: `.` as the thousands separator, the total including IVA, and UF mapped to `CLF`.
- **Dependencies:** `httpx` moves to main dependencies, because it is used to download Gmail attachments from `s3url`.
