# Risks & Mitigations

## Technical Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Generic top-level package names (`api`, `core`, `contracts`, `modules`) can shadow or collide with site-packages of the same name | med | `backend/` is the uv project root and `sys.path[0]` — local packages win. Never `pip install` a package named `api`/`core`/`contracts` into the venv; add an ruff `isort` known-first-party config. Revisit with a brand namespace if it ever bites. |
| `deepagents` API for passing a custom checkpointer/model instances varies by version (v0.7 fast-moving) | med | Pin `deepagents>=0.7` and verify the exact kwarg (`checkpointer=` vs `.compile(checkpointer=...)`) against the installed version at implementation time; isolate the construction in `orchestrator/service.py` / `payments/agent.py` so a fix is local. |
| OpenRouter via `ChatOpenAI(base_url=...)` may not support every feature (tool-calling edge cases, streaming deltas) | med | Keep models configurable; the gateway is the single swap point. If OpenRouter streams oddly, fall back to `astream_events` v2 aggressive buffering for tokens. |
| In-process background runs die on restart/reload (uvicorn `--reload` during dev kills tasks) | high | Accepted by design (user chose in-process). Persist `pending/running` rows BEFORE spawning the task; startup sweep marks orphans failed; clients poll status and see the terminal failure. For the hackathon demo, avoid reloading mid-run. |
| LangGraph `AsyncPostgresSaver.setup()` runs at every startup against PG-2/PG-3 | low | `setup()` is idempotent (CREATE IF NOT EXISTS). Cheap enough; no custom migration needed. |
| 3 Postgres instances + MinIO on a laptop is heavy but bounded | low | Compose uses healthchecks + `restart: unless-stopped`; each PG gets `shared_buffers=128MB` tuning via command args if needed. |
| MinIO bucket bootstrap race (multiple workers) | low | Single uvicorn process in base; bucket creation uses `head_bucket` → `create_bucket` on `BucketAlreadyOwnedByYou` no-op. |
| aioboto3/aiobotocore version pinning friction on Python 3.13 | med | Pin `aioboto3>=13`; if unusable on 3.13, swap to `obstore` (Rust, async) behind the same `StorageBackend` protocol — only `modules/files/storage.py` changes. |
| JWT with no refresh: 60-min expiry mid-demo | low | Acceptable for base; config knob `jwt_expire_minutes`. Refresh flow is a later add. |
| Alembic multi-DB sections are easy to get wrong (env.py name resolution) | med | Use `alembic -n product` / `-n payments` sections with one `env.py` reading `-x`/name; document exact commands in the module spec; smoke-test `upgrade head` for both sections in the base phase. |

## Integration Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Turbo/pnpm breakage after moving `apps/*` to root folders | med | Update `pnpm-workspace.yaml`, `turbo.json` task outputs, and both package.json names in the same commit; verify `pnpm install` + `pnpm dev` immediately. |
| Frontend (Next 16) expects nothing from backend restructure, but proxy/base URLs may hardcode ports | low | Backend stays on :8000 (unchanged); frontend untouched apart from the move. |
| Guardrail stub returning `allowed=True` for everything means the 422 path is never exercised | med | Wire the exception handler + contract anyway; add a documented env kill-switch in the stub (`BLINKA_GUARDRAILS__ENFORCE` default false→true later) so the rejection path is testable before real screens exist. |
| `initiate_payments` tool runs inside the agent loop but must not block it on a full payment run | high | The tool ONLY enqueues the background run and returns the run_id immediately (fire-and-forget); the runner owns execution. Contract states this explicitly. |
| SessionService dual-DB writes are not transactional across PG-1/PG-3 | low | By design: mutable session state and immutable execution log are independent records; no cross-DB invariants are claimed. |

## Edge Cases Identified

- **Duplicate invoice upload** (same file twice): each upload is a new `file_id`; dedup is out of scope for base.
- **Upload of unsupported format** (e.g. .exe): stored + `parse_status=unsupported`; agents receive a reference, not content.
- **Payment run triggered with a non-invoice file_id**: invoice parse fails → run transitions to `failed` with event `invoice_parse_failed`.
- **Polling for an unknown run_id**: 404 `run not found`.
- **Chat with `file_ids` not owned by the JWT user**: `FilesService.get_context` filters by `owner_id` → 404 semantics (not 403, avoid existence leaks).
- **Streaming client disconnects mid-SSE**: agent graph run is cancelled; checkpoint up to last node persists in PG-2; conversation continues on next request with same `session_id`.
- **Concurrent chats on the same session_id**: LangGraph checkpointer serializes per thread; last-write wins per turn — documented behavior, no extra locking in base.
- **Email-triggered flow**: stub — `invoice_ingestor` service method is the future entry point; no listener code written.
