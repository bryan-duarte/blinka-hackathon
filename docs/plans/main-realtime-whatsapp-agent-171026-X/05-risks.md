# Risks & Mitigations

## Technical Risks

| Risk | Impact | Mitigation |
|---|---|---|
| The deepagents harness profile does not match the OpenRouter-backed `ChatAnthropic` provider key, so filesystem and `task` tools leak into the agent | med | Assert the exact tool set at build time and fail loudly. Fallback: resolve the key with `get_model_provider(model)`, or replace `FilesystemMiddleware` by name |
| The agent loops, skips steps or stops before settling | high | Tools take no arguments and enforce order. `recursion_limit=40`. `_finalize` fails closed to REVIEW once a bill is claimed, and otherwise marks `agent_incomplete` |
| The agent adds LLM latency (planning plus tool turns) on top of the 3 existing LLM calls | med | Haiku-class `payments` model and compact tool outputs. The live UI makes the wait visible, and it is the demo value |
| A prompt-injection invoice steers the agent | high | Raw text never enters agent messages. Tools take no inputs. The verdict comes only from deterministic rules plus the checker |
| AppSync publish failures or latency slow or break the pipeline | med | Best-effort publish with a 5 s timeout. Errors are logged and swallowed. `NullRealtimeBackend` when disabled |
| A token stream floods AppSync (cost, 25 publishes/s per connection limit) | med | Coalesce every 400 ms and publish only. Tokens are never persisted |
| The `dns` map keys differ from `HTTP`/`REALTIME` | low | Confirm with `terraform console` after the first apply (spike task) |
| Amplify Events API is `@experimental` | low | Pinned to 6.22.2. The hook isolates the API, so a raw WebSocket fallback stays possible |
| Payments alembic autogenerate tries to drop the LangGraph `checkpoint*` tables | high | Review the generated migration by hand and delete those ops (called out in spec 01) |
| `RUN_EVENT_LIST_LIMIT=100` truncates the timeline once tool events exist | med | Raise it to 300 |

## Integration Risks

| Risk | Impact | Mitigation |
|---|---|---|
| The Kapso sandbox-session API is undocumented (404) | med | Spike first. `create_sandbox_session` returns `None` and the UI falls back to manual instructions |
| The sandbox may not deliver `document` messages or `media_url` | high | Spike first. Fallback through media id to `download_url`. Simulated WhatsApp samples keep the demo working without a phone |
| A public HTTPS webhook URL is needed for Kapso in local dev | med | `BLINKA_KAPSO__WEBHOOK_URL` plus ngrok. The bootstrap script prints the hint |
| Coexistence numbers are less stable, and some first inbound messages may be missed | low | Offer dedicated as well. Handle reconnects later through `whatsapp.phone_number.disconnected` (out of scope) |
| The shared sandbox only holds one active project session per phone, so another Kapso project can take a tester phone over | low | Documented. The user re-activates |
| The API key is public in the browser, so anyone with key plus user UUID can listen to that user's events | med (accepted) | Accepted for the hackathon. Publish needs IAM. Upgrade path: a Lambda authorizer on the existing JWT |
| Removing sessions or chat breaks an unseen consumer | low | Grep confirmed no frontend or test usage. Keep `BillSourceType.CHAT` for legacy rows |
| Moving to the instance role later | low | Default credential chain. `aws_profile=None` switches with no code change. The policy is a reusable document |

## Edge Cases Identified

- **Duplicate webhook deliveries** (Kapso retries at about +10 s and +40 s) are deduped by `UniqueConstraint(provider, external_message_id=wamid)`.
- **Batched webhook payloads** (`data[]`) are unwrapped even though `buffer_enabled=false`.
- **Coexistence echoes** (`origin=business_app`) and history sync are filtered by `direction == "inbound"`.
- **Documents over 10 MB** are rejected, and the item ends in `error` with "whatsapp provider unavailable" / "document too large".
- **Non-accepted extensions** (`.docx`, images, voice) are ignored at the webhook and not stored.
- **A phone registered by another user in sandbox** returns 409 "phone already registered". The partial unique index enforces this at the DB level.
- **A user connects their own number while the sandbox is active.** The sandbox row expires, so routing uses only the own number.
- **Duplicate bill, or no bill** (`not_a_bill`, `extraction_failed`): the agent stops on `"final": true`. `_finalize` treats it as a no-op.
- **Server restart mid-run:** the existing startup sweeps mark runs and inbox items failed. The checkpointer thread for that run is simply abandoned.
- **Socket drops mid-run:** the page falls back to 4 s polling. `AgentActivity` re-fetches persisted events and dedupes by `sequence`, so only thinking text is lost.
- **Events arrive out of order:** sort by `sequence`. A terminal event triggers a REST refetch of the item, which is the source of truth.
- **Frontend has no realtime env vars:** behaves exactly like today, with polling.
