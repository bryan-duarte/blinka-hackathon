# User Preferences & Decisions

## 👤 Configuration Preferences

- **Context Level**: Moderado
- **Participation Level**: Control pleno
- **Detail Level**: Neutral

## 💬 Q&A and Rationale

### 🏷️ Payments agent

**Q:** What role should the new deep agent have?
**A:** The agent drives step tools.
**Decision:** `create_deep_agent` plans with `write_todos` and calls 6 tools: `classify_document`, `extract_invoice`, `register_bill`, `evaluate_rules`, `run_checker`, `settle_decision`. The verdict is computed only by `rules.decide` + `apply_checker` inside the tools. No tool accepts a verdict argument.
**Rejected:** Checker-only agent (too few visible tool calls). Free-form verdict (breaks the "never exceed limits" guarantee).

**Q:** Which builder?
**A:** `create_deep_agent` + `TodoListMiddleware`.
**Decision:** `deepagents.create_deep_agent(..., middleware=[TodoListMiddleware()])`. A harness profile excludes the filesystem/execute tools and disables the general-purpose subagent, so the final tool set is exactly the 6 step tools plus `write_todos`.
**Rejected:** `langchain.create_agent` (the user asked for the deepagents native tool). All defaults (noise in a payments agent).

**Q:** Fail-safe when the agent doesn't settle?
**A:** Fail closed to REVIEW.
**Decision:** After the agent returns, the runner checks run state. If a bill is claimed but undecided, it calls `fail_closed` and records `decision_failed`. If no bill was claimed and the run is not a terminal non-bill, the run is FAILED with `agent_incomplete`. `recursion_limit=40`.
**Rejected:** Retry (adds latency). Fallback pipeline (two code paths).

**Q:** Model?
**A:** `llm.model("payments")` (`BLINKA_LLM__PAYMENTS_MODEL`).
**Decision:** Reuse the existing setting.
**Rejected:** The main model (cost). A new model kind (unneeded config).

**Q:** Prompt injection?
**A:** Structured summaries only.
**Decision:** Tool outputs are compact typed dicts. Raw document text and email body never enter the agent's messages. `embedded_instructions` is surfaced only as a count plus the flag `has_embedded_instructions`.
**Rejected:** Raw text in tags (more injection surface).

### 🏷️ Orchestrator removal

**Q:** Cleanup scope?
**A:** Full removal + migrations.
**Decision:** Delete:
- orchestrator, chat router, diagnostics router, `contracts/chat.py`
- the `main_agent` and `hello_world` prompts
- the tools module and client, `contracts/tools.py`
- the sessions module, client and contracts
- `PaymentRunTrigger.session_id` and `AgentRun.session_id`

Migrations drop the `sessions` table (product), `agent_runs.session_id` (product) and `session_executions` (payments). Keep `BillSourceType.CHAT` for legacy rows.
**Rejected:** Keeping the tables (dead schema). Orchestrator-only removal (orphans).

**Q:** Agent DB?
**A:** Drop the agent DB and reuse the payments checkpointer.
**Decision:** Remove:
- `postgres-agent` (docker-compose)
- `BLINKA_AGENT_DATABASE_URL`
- `Pools.agent`
- `Checkpointers.agent`

The agent uses `checkpointers.payments` with `thread_id=str(run_id)`.
**Rejected:** Keeping both (unused infra). No checkpointer (no state inspection).

### 🏷️ Realtime events

**Q:** Persist agent events?
**A:** Persist + publish.
**Decision:** Every run step, tool start/finish, todos snapshot and the final agent summary is written to `agent_run_events`, then published. `GET /payments/runs/{id}` replays the history.
**Rejected:** Ephemeral only (lost on refresh).

**Q:** Which events are realtime?
**A:** All of them: inbox item status, run steps, agent tool calls + todos, and LLM tokens. **User note:** "The tools messages need to be randomly from a list of options depending of the tool, like 'Clasificando la factura, bla bla bla', also legible."
**Decision:** A per-tool catalog of 3–5 legible Spanish phrases for start and for finish. One is picked at random per event.
**Rejected:** —

**Q:** Token handling?
**A:** Coalesce, live only.
**Decision:** Buffer `on_chat_model_stream` text and flush one `agent.thinking` event every 400 ms. Never persisted. The final AI message is persisted once as the `agent_summary` step.
**Rejected:** Persisting deltas (row explosion). Per-token publish (cost).

**Q:** Where are friendly tool messages picked?
**A:** In the backend, and stored.
**Decision:** `modules/payments/phrases.py` picks the message, which is stored in `payload["message"]`, so live and reload show the same text.
**Rejected:** Picking in the frontend (text changes between renders).

**Q:** Channel scope?
**A:** Per user, one channel.
**Decision:** Namespace `inbox`, channel `/inbox/{owner_id}` (a UUID with dashes is valid). Every event carries `item_id` / `run_id` for client-side routing.
**Rejected:** Per-run channels (more subscriptions). Run-only (list still polled).

**Q:** Subscribe auth?
**A:** API key + unguessable channel.
**Decision:**
- Namespace `inbox`: `subscribe_auth_mode=API_KEY`, `publish_auth_mode=AWS_IAM`.
- `connection_auth_mode=API_KEY`.
- The browser gets the API key through `NEXT_PUBLIC_APPSYNC_EVENTS_API_KEY`.
**Rejected:** Lambda authorizer (more infra for a hackathon). Backend-minted tokens.

**Q:** Publish auth?
**A:** "For now this can use my current role, but later in the deploy we gonna attach an IAM role to the instance."
**Decision:** SigV4 with the default AWS credential chain. `aws_profile` is optional (the current `panoptico` profile now, the instance role later with no code change). Terraform defines the publish policy as an `aws_iam_policy_document` attached to `var.backend_iam_user` now, reusable for a role later.
**Rejected:** API-key publishing (lets the browser publish).

**Q:** Frontend client?
**A:** `aws-amplify` v6 events.
**Decision:** `aws-amplify@6.22.2`, `events.connect('/inbox/{userId}')`.
**Rejected:** A raw WebSocket hook.

**Q:** Polling?
**A:** Realtime first, slow fallback.
**Decision:** While the socket is live there is a 60 s safety refresh. While it is connecting or offline, the current 4 s / 15 s inbox polling applies. Every (re)connect does a REST resync.
**Rejected:** Removing polling. Keeping polling as is.

**Q:** Agent view?
**A:** Replace `RunTimeline`.
**Decision:** A new `AgentActivity` component shows:
- the plan checklist
- the tool feed with friendly messages and durations
- a muted thinking line

When the run finishes it collapses to a summary, and stays shown above the decision card.
**Rejected:** Both components side by side. Inline in the list.

### 🏷️ WhatsApp (Kapso)

**Q:** Data model?
**A:** Reuse the inbox tables.
**Decision:**
- Add `MailProvider.WHATSAPP`.
- WhatsApp connections live in `mailbox_connections`, with new nullable columns `mode`, `phone_number` and `external_ref`.
- Messages live in `inbox_emails` (sender = contact/phone, subject = filename, body = caption).
- `source_type` is derived from `provider`.
**Rejected:** Renaming the tables (big diff). Separate tables (duplicate wiring).

**Q:** Accepted files?
**A:** PDF + ZIP/XML.
**Decision:** WhatsApp `document` messages whose filename extension is in `EVIDENCE_MIME_BY_EXTENSION` (`.pdf`, `.zip`, `.xml`).
**Rejected:** PDF only.

**Q:** Sandbox join?
**A:** API session + manual fallback. **User note:** "This is only if the user wants to connect their number; if not, the platform uses the sandbox number by default."
**Decision:**
- The WhatsApp card defaults to sandbox mode.
- The user registers their phone. The backend tries Kapso's sandbox-session API for an activation code and `wa.me` link. On any failure it returns `activation=None`, and the UI shows the sandbox number with manual dashboard instructions.
- "Conectar mi número" is the opt-in path.
- Activating an own number sets the user's sandbox connection to `expired`.
**Rejected:** Manual only. Our own demo number (cost).

**Q:** Sandbox owner mapping?
**A:** The user registers their phone.
**Decision:**
- Route sandbox messages by `conversation.phone_number`, normalized E.164, to the `mailbox_connections` row with `mode='sandbox'` and status `active`.
- A partial unique index `(phone_number) WHERE mode='sandbox' AND status='active'` keeps one owner per phone.
- Unknown senders are ignored.
**Rejected:** A single demo owner. A hybrid fallback.

**Q:** Own-number connection types?
**A:** Coexistence + dedicated.
**Decision:** `allowed_connection_types=["coexistence","dedicated"]`, `language="es"`.

**Q:** Webhook registration?
**A:** Automatic per number.
**Decision:**
- On confirm, the backend registers a phone-number webhook (`whatsapp.message.received`, v2, unbuffered) and stores the webhook id in `trigger_id`.
- The sandbox number's webhook is registered by `scripts/bootstrap_kapso.py`.
- One Kapso customer per Blinka user (`external_customer_id=str(owner_id)`).
**Rejected:** Manual setup in the dashboard.

**Q:** Non-bill messages?
**A:** Ignore, don't store.
**Decision:** Drop them in `parse_webhook` (debug log only).

**Q:** Replies to the sender?
**A:** No replies.
**Decision:** Read-only intake.

**Q:** UI scope?
**A:** All of: WhatsApp connection card, neutral copy, simulated WhatsApp samples, source filter.
**Decision:** See `06-implementation/08-frontend-whatsapp/spec.md`.

## Assumptions made by the agent

- Kapso success redirect → a dedicated page `/inbox/whatsapp/callback`, to avoid query-string collisions with the Composio callback.
- `POST /webhooks/whatsapp` returns 200 (Kapso expects a 2xx within 10 s). Heavy work is spawned in the background.
- Idempotency comes from the existing `UniqueConstraint(provider, external_message_id)` using the WhatsApp `wamid`. `X-Idempotency-Key` is not stored.
- The frontend gets `userId` by decoding the `sub` claim of the stored JWT, with no verification. Verification isn't needed for channel selection; the channel is the only secret.
- LLM prompts keep their `<email_body>` envelope wording. Only UI copy becomes channel-neutral.
