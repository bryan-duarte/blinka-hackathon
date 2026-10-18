# User Preferences & Decisions

## 👤 Configuration Preferences

- **Context Level**: Moderado
- **Participation Level**: Equilibrado
- **Detail Level**: Neutral (snippets are orientative; implementer decides final code)

## 💬 Q&A and Rationale

### 🏷️ Bedrock migration
**Q:** Which LangChain class replaces ChatAnthropic-over-OpenRouter?
**A:** ChatBedrockConverse.
**Decision:** Add `langchain-aws` and build `ChatBedrockConverse` in `LlmGatewayService._build_chat_model`. The PDF block in `invoice_ingestor` is already the LangChain standard `{"type":"file",...}`, which Converse supports. Only the filename needs sanitizing.
**Rejected:** ChatBedrock (InvokeModel) fails on standard `file` blocks and is less provider-neutral.

**Q:** What happens to OpenRouter?
**A:** Remove entirely.
**Decision:** Delete `LlmSettings.base_url` and `api_key` (`OPENROUTER_API_KEY`), the `OPENROUTER_API_KEY` SSM parameter, and the `.env.example` lines. Remove `langchain-anthropic` only if nothing else imports it. langmem pulls it in transitively anyway, which is fine.
**Rejected:** A switchable provider adds code paths nobody asked for.

**Q:** Which models?
**A:** Haiku 5.5 for everything.
**Decision:** `BLINKA_LLM__MODEL=global.anthropic.claude-haiku-5-5`, the ID quoted verbatim in the AWS launch blog (2026-10-07). `main_model` and `payments_model` stay as optional overrides and default to unset. A task verifies the ID with `aws bedrock list-inference-profiles` and confirms model access before deploy. `us.anthropic.claude-haiku-5-5` is the US-geo alternative if data must stay in US regions; set it via SSM.
**Rejected:** Sonnet main/Haiku payments split. User chose one cheaper model.

**Q:** How to resolve aioboto3 15.5 pinning botocore 1.40, which caps langchain-aws at 1.1.0?
**A:** Swap aioboto3 for aiobotocore 3.x.
**Decision:** Replace `aioboto3` with `aiobotocore` in four adapters: textract, guardrails, storage, appsync. All four only use clients. This unlocks langchain-aws ≥1.4 (target the latest resolvable, 1.9.x), which brings `BedrockPromptCachingMiddleware`. deepagents adds it automatically.
**Rejected:** Staying on 1.1.0 means no prompt caching and thread-pooled async.

### 🏷️ Private networking
**Q:** Which interface endpoints?
**A:** `bedrock-runtime` only.
**Decision:** One `aws_vpc_endpoint` (Interface, `private_dns_enabled=true`) in `aws_subnet.app[*]`, with a new `aws_security_group.vpce` that allows 443 from `aws_security_group.app`. The NAT stays for Composio, Kapso and FX. The existing ApplyGuardrail calls and Titan embeddings also go through this endpoint automatically.
**Rejected:** Textract, ECR and logs endpoints were out of scope and cost about 6x more.

### 🏷️ Agent run limits
**Q:** How to enforce?
**A:** Middleware plus asyncio.timeout.
**Decision:** Add `ToolCallLimitMiddleware(run_limit=N, exit_behavior="error")` and `ModelCallLimitMiddleware(run_limit=M, exit_behavior="error")` to `create_deep_agent(middleware=[...])`, and wrap `stream_agent` in `asyncio.timeout(T)`. Keep `AGENT_RECURSION_LIMIT=80` as a backstop.
**Rejected:** A custom counter in `_run_serialized` duplicates what the middleware already does and has no model-call cap.

**Q:** What happens when a limit is hit?
**A:** Escalate to a human.
**Decision:** Raise a typed `AgentLimitExceededError` and record it on `RunState.limit_exceeded`. `_finalize` calls `fail_closed(..., explanation=<limit text>)`, so the bill goes to REVIEW. If no bill was claimed yet, the run ends FAILED with the limit reason.
**Rejected:** Hold the bill (it sits unnoticed). Failed only (least visible).

**Q:** Defaults?
**A:** 180 s, 30 tools, 35 model calls. Revised after I corrected my count: a clean run is about 13 tool calls and 14 model calls.
**Decision:** A new `AgentSettings` group with env prefix `BLINKA_AGENT__`, holding global settings. Per-company limits are not possible because the policy loads only in `register_bill`.
**Rejected:** 20/25 left only about 1.5x headroom.

**Q:** UI for limit hits?
**A:** A dedicated node.
**Decision:** A new run step `limit_exceeded` with payload `{limit: "time"|"tool_calls"|"model_calls", threshold: number}`, a `STEP_PHRASES` entry, a `runEvents.ts` extractor, and a `RunTimeline` node.

### 🏷️ Long-term memory
**Q:** Storage?
**A:** langmem with AsyncPostgresStore.
**Decision:** `create_memory_store_manager` writes `{"kind": "PaymentPrecedent", "content": {...}}` items into LangGraph `AsyncPostgresStore` in `blinka_agent`, reusing the checkpointer's psycopg pool. No custom SQLAlchemy table.
**Rejected:** A custom AgentBase table would be a non-standard format.

**Q:** Retrieval?
**A:** Semantic, with pgvector and Titan.
**Decision:** Store `index={"dims":1024, "embed": BedrockEmbeddings("amazon.titan-embed-text-v2:0"), "fields":["content.situation","content.lesson"]}`. Enable the pgvector extension in `core/db/bootstrap.py` and in the local compose image.
**Rejected:** Filter-only retrieval is recency-ranked and weakens langmem's consolidation.

**Q:** How do memories reach the agent, and what can they influence?
**A:** Advisory context for the checker and the agent.
**Decision:**
- Retrieve after `register_bill`, once the payee is known. The `register_bill` tool output gets `precedents: [...]`, and the checker user content gets a `<human_precedents>` block.
- Both prompts state that precedents are advisory: they can explain or shift checker probabilities, but never waive caps, blacklist, budget or allowlist.
- The deterministic `decide()` never reads memories.
**Rejected:** A `search_memory` tool is unpredictable and spends tool budget. Explanation-only would leave the precedents unused.

**Q:** Which actions offer "Remember this"?
**A:** Approve and reject.

**Q:** When does extraction run?
**A:** In a background task.
**Decision:** After approve/reject settles, `PaymentsService` calls `memory.remember_decision_later(...)`, which `ExecutionRegistry.spawn`s the langmem call. Failures are logged and don't affect the decision. It is not durable: a restart loses in-flight extractions (accepted).

**Q:** Namespace?
**A:** Owner plus payee.
**Decision:** `("payments_memories", str(owner_id), payee_key)`, where `payee_key = str(bill.payee_id)`, or `"name:" + normalize_name(bill.payee_name)` when there's no matched payee. Precedents don't transfer across payees.
**Rejected:** Owner-only with payee as metadata.

**Q:** Management UI?
**A:** A settings page that lists and deletes memories.
**Decision:** `/settings/memories` with `GET /memories` and `DELETE /memories/{namespace_key}/{memory_id}`, grouped by payee, showing source bill, action, note excerpt and date.

**Q:** Demo reset?
**A:** Wipe on reset.
**Decision:** `DemoService.reset` calls `memory.forget_owner(owner_id)`, which deletes every item under the prefix `("payments_memories", owner_id)`.

### 🏷️ Agent-decided (not asked)
- **Memory schema:** one schema, `PaymentPrecedent` (semantic/episodic hybrid). See 03-design.md.
- **Source metadata:** after langmem writes, re-`aput` each item with a top-level `"source"` dict (bill_id, decision_verdict, actor_user_id, note excerpt, decided_at). langmem only reads `kind` and `content`, so the extra key is safe. It is overwritten on a langmem update and re-attached on each extraction.
- **No `create_manage_memory_tool`:** it writes items without `kind`, which breaks the manager in the same namespace (KeyError).
- **Memory LLM:** `llm_gateway.model("main")`, which resolves to Haiku 5.5.
- **Feature flag:** `BLINKA_MEMORY__ENABLED` (default true) so local dev without pgvector or Bedrock can boot.
