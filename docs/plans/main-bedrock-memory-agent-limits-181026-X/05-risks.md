# Risks & Mitigations

## Technical Risks

| Risk | Impact | Mitigation |
|---|---|---|
| The Haiku 5.5 inference-profile ID or model access isn't enabled in the account. | high | Run the verify task (`list-inference-profiles`) before deploy. The ID is a setting, so you can fix it in SSM without code. Haiku 4.5 (`us.anthropic.claude-haiku-4-5-20251001-v1:0`) is the fallback. |
| `global.*` CRIS can route requests outside US regions, which raises a data-residency question for financial documents. | med | If residency matters, set `BLINKA_LLM__MODEL=us.anthropic.claude-haiku-5-5` (after verifying it). IAM already covers both forms through wildcards. |
| Haiku 5.5 can return a reasoning block before the text block. | med | `message_text` and the JSON-mode fallback must read `text` blocks only. With thinking off by default, `with_structured_output` (forced tool choice) is unaffected. |
| If the harness profile isn't registered for `amazon_bedrock`, filesystem tools come back. | high | Register the profile for both providers. `tests/test_payments_agent.py:166,278` asserts the tool set. Update the fake model's `ls_provider` to `amazon_bedrock` so the test exercises the new path. |
| The aiobotocore port breaks S3, Textract, the guardrail or the AppSync signing. | med | All four are client-only. Keep the lazy `__aenter__` pattern and run the existing evidence, realtime and guardrail tests. `AioSession.get_credentials()` is async in aiobotocore. |
| The resolver still picks an old langchain-aws, so prompt caching is missing. | low | Remove aioboto3 **first**, then add the others. Check `uv.lock` for `langchain-aws` ≥1.4. |
| langmem is pre-1.0 and lightly maintained (0.0.30). | med | Use only `create_memory_store_manager` and its documented value shape. All langmem access goes through `MemoryService`, so a replacement only touches one file. |
| langmem `ConfigurationError` subclasses `BaseException`, so `except Exception` won't catch it. | med | The manager namespace uses the `{owner_id}`/`{payee_key}` templates. Always pass both in `config["configurable"]`, and catch `(Exception, ConfigurationError)` explicitly in the background task. |
| pgvector is missing locally (the dev containers on 55434) or the RDS user can't run `CREATE EXTENSION`. | med | Bootstrap creates the extension. `BLINKA_MEMORY__ENABLED=false` lets the app boot without it. Recreate the dev container from `pgvector/pgvector:pg17`. |
| Alembic autogenerate tries to drop the LangGraph store tables. | med | Extend `_include_name` in `alembic/env.py`. |
| Wall-clock timeout cancels a tool mid-settlement. | high | `settle` is atomic (`commit_settlement` runs in one transaction). If a payment was reserved, `fail_closed` finds it via `payment_for_bill` and executes the recovered payment. No double-settle is possible because of the bill-status CAS. |
| Prompt injection through stored memories: a malicious invoice influences a human note, which becomes a memory, which steers future runs. | med | Memories are advisory and never reach `decide()`. They come only from authenticated human notes. The prompts state that hard rules always win. The settings page allows deletion. |

## Integration Risks

| Risk | Impact | Mitigation |
|---|---|---|
| The SSM `operator_params` have `ignore_changes=[value]`, so the old `anthropic/...` model IDs remain live. | high | Move `BLINKA_LLM__MODEL` to `managed_params` with a `moved {}` block, or delete and recreate it. Remove the `MAIN_MODEL`/`PAYMENTS_MODEL` params so the stale OpenRouter IDs can't override. |
| Removing the `OPENROUTER_API_KEY` SSM param while the old task definition still references it. | med | `deploy.sh` registers a new task def without it. Apply Terraform and deploy in the same window. The old key in `backend/.env` (`sk-or-v1-…`) should be rotated or revoked after cutover. |
| The VPC endpoint's private DNS changes resolution for the existing ApplyGuardrail calls. | low | That's intended (it makes them private too). The same IAM applies and the endpoint policy is full-access by default. |
| Cross-region inference through an endpoint in the source region is inferred from docs, not stated explicitly. | med | After deploy, verify with an ECS Exec smoke call (`aws bedrock-runtime converse` from the task) and check VPC endpoint metrics (bytes processed > 0). |
| The ECS execution role needs no change, but the task role lacks `InvokeModel`. | high | The new `backend_bedrock_invoke` policy covers it. Attach it to `var.backend_iam_user` as well for local dev. |
| The Titan embedding call fails, so the store put fails, so memory isn't saved. | low | It runs in the background, the failure is logged as `memory_extraction_failed`, and the decision is unaffected. |
| Frontend sends `remember` to an old backend. `ApiModel` has `extra="forbid"`, so the old backend returns 422. | low | Deploy the backend before the frontend. |

## Edge Cases Identified

- **Bill without a matched payee and without a payee name:** `payee_key_for` returns `None`. Skip memory capture (log `memory_skipped_no_payee`) and skip recall.
- **Approve fails and fail-closes back to REVIEW:** don't save memory, since the decision never happened. Only call `remember_decision_later` on the `else:` branch.
- **Approve re-settles as HOLD** (budget exhausted at approval time): still save, with `human_action="approved"` and `resulting_verdict=hold`. The lesson is about the human's intent.
- **Two approvals racing:** the second gets a 409 from `_claim_review` before any memory work, so there's no duplicate memory.
- **The same lesson remembered twice:** the langmem manager searches the namespace (`manager_query_limit=10`) and updates the existing item instead of inserting a new one.
- **Note is pure noise** ("ok", "fine"): the manager may extract zero memories. That's fine and is logged with `count=0`.
- **Limit hit before `register_bill`:** there's no bill. The run goes FAILED with reason `limit_exceeded:<limit>`. The inbox shows ERROR, the same as other early failures.
- **Limit hit after settlement** (agent loops writing todos after `"final": true`): `state.decision` is set, so `_finalize` returns early. The decision stands, and the `limit_exceeded` step is still recorded.
- **Demo reset while a background extraction is running:** the extraction may write after the wipe. `MemoryService` has its own `ExecutionRegistry` and spawns with `owner_id`. Demo reset calls `memory.cancel_owner` before `forget_owner`.
- **Deleting a memory the manager is updating:** last write wins. That's acceptable for a single-user tenant.
