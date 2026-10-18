# Technical Design

All backend paths are relative to `backend/`.

## Architecture Decisions

1. **The LLM provider is Bedrock through `ChatBedrockConverse`, behind the existing `LlmGatewayService`.** Callers (`runner.py:82`, `checker.py:43`, `invoice_ingestor/service.py:68,185`) depend only on `BaseChatModel` and `extract()`, so the swap is contained in `modules/llm_gateway/service.py` and `core/config.py`.
2. **AWS SDK is `aiobotocore` 3.x, replacing `aioboto3`.** This removes the botocore 1.40 pin so `langchain-aws` can resolve to ≥1.4, which enables prompt caching. Every adapter keeps its lazy-client pattern (`self._client_context.__aenter__()`).
3. **Private path: one `bedrock-runtime` interface endpoint with private DNS.** No code passes `endpoint_url`. The regional hostname resolves to the endpoint ENIs inside the VPC. Local dev keeps using the public endpoint through the `panoptico` profile.
4. **deepagents harness profile is registered for both `"anthropic"` and `"amazon_bedrock"`.** `ChatBedrockConverse` reports `ls_provider="amazon_bedrock"`. Without this, the filesystem tools leak back into the payments agent.
5. **Run limits = middleware (tool/model counts) + `asyncio.timeout` (wall clock), all raising.**
   - Everything converges on `AgentLimitExceededError(limit, threshold)`, which is caught in `runner._run_agent`.
   - It escalates through the existing `fail_closed(explanation=...)`.
   - `exit_behavior="error"`, not `"end"`, because `"end"` would let the run finish "cleanly" without a decision, and `_finalize` would fail-close with a generic message.
6. **Memory = new `modules/memory` module that owns an `AsyncPostgresStore` and a langmem `MemoryStoreManager`.**
   - The store lives in `blinka_agent`, shares the psycopg pool with the checkpointer, and is created in `Checkpointers.open()` (renamed responsibility: agent persistence).
   - Memory is advisory only. `rules.decide()` never sees it.
7. **Memory capture is fire-and-forget after settlement** (`ExecutionRegistry.spawn`), triggered only when `ReviewActionRequest.remember is True`.
8. **Memory retrieval happens inside `register_bill`**, the first point where the payee is known.
   - Results go on `RunState.precedents`.
   - They are echoed in the tool output (the agent sees them) and passed into `DecisionContext.precedents` (the checker sees them).
   - Retrieval failure means no precedents (logged). It never fails the run.

## Patterns & Conventions

- **Module layout:** mirror `modules/fx`: `__init__.py` (re-exports and `__all__`), `errors.py` (`MemoryError` base → name it `AgentMemoryError` to avoid shadowing the builtin), `service.py`, `schemas.py` (langmem pydantic schemas). The client is `clients/memory.py`, with the service imported under `TYPE_CHECKING`, mirroring `clients/fx.py`.
- **Contracts:** `contracts/memory.py`. Use `StrictModel` for internal records and `ApiModel` for HTTP (`contracts/_base.py`).
- **Settings:** a new `BaseSettings` group per concern with `env_prefix="BLINKA_<GROUP>__"`, `env_file=".env"`, `extra="ignore"`, `frozen=True`, nested in `Settings` via `Field(default_factory=...)` (`core/config.py`). Use `Field(ge=, gt=)` for validation, like `WorkerSettings`.
- **AWS adapters:** keep `aws_profile: str | None` plus region per settings group. A profile of `None` means the default chain, which is the ECS task role.
- **Errors → HTTP:** add entries to `DOMAIN_ERROR_RESPONSES` in `api/app.py:66-106` (`MemoryNotFoundError` → 404).
- **Routers:** `api/routers/memory.py` with `CurrentUserDep` and `ClientsDep`, mounted in `api/routers/__init__.py`.
- **Events:** step constants in `modules/payments/events.py:19-39`, phrases in `modules/payments/phrases.py` `STEP_PHRASES`, emitted via `RunEventRecorder.step(step, payload)`.
- **Logging:** `logger = get_logger(__name__)` with snake_case event names (`memory_extraction_failed`, `payments_agent_limit_exceeded`).
- **Dependencies:** CLI only (`uv add`, `uv remove`, `pnpm add`). Never hand-edit `pyproject.toml` pins or lock files.
- **Frontend:** follow `frontend/DESIGN.md` (re-read it fully before UI work; it changes often). Settings pages mirror `app/settings/blacklist/page.tsx`. API methods go in `lib/api.ts`, types in `lib/types.ts`.

## Dependencies

| Action | Package | Command | Notes |
|---|---|---|---|
| add | `langchain-aws` | `uv add langchain-aws` | Expect ≥1.9 once aioboto3 is gone (needs `boto3>=1.43.64`, `langchain-core>=1.6.10`) |
| add | `aiobotocore` | `uv add aiobotocore` | 3.x (botocore 1.43.x) |
| remove | `aioboto3` | `uv remove aioboto3` | Do this **before** adding langchain-aws so the resolver picks a modern botocore |
| add | `langmem` | `uv add langmem` | 0.0.30. Pulls `trustcall`, `langchain-openai`, `langchain-anthropic` transitively |
| maybe remove | `langchain-anthropic` | `uv remove langchain-anthropic` | Direct dep only. It stays installed transitively via langmem, which is harmless |
| none | `langgraph-checkpoint-postgres` | n/a | Already provides `langgraph.store.postgres.AsyncPostgresStore` (3.2.0) |
| infra | pgvector | compose image `pgvector/pgvector:pg17` | RDS PG17 supports `CREATE EXTENSION vector` without preload |

Order: `uv remove aioboto3` → `uv add aiobotocore langchain-aws langmem` → check that `uv.lock` shows `langchain-aws>=1.4`.

## Integration Points

| Where | What changes |
|---|---|
| `core/config.py:17-29` `LlmSettings` | Drop `base_url` and `api_key`. Add `aws_profile`, `aws_region`, `connect_timeout_s`. Set `model` default to `global.anthropic.claude-haiku-5-5` |
| `core/config.py` | Add `AgentSettings` (`BLINKA_AGENT__`) and `MemorySettings` (`BLINKA_MEMORY__`), and wire both into `Settings` |
| `modules/llm_gateway/service.py:95-104` | `_build_chat_model` returns `ChatBedrockConverse(...)` |
| `modules/invoice_ingestor/service.py:236-247` | `filename` → `_converse_document_name(attachment.file.filename)` |
| `modules/payments/agent.py:23,42,45-58,61-72` | Dual harness registration. `build_payments_agent(..., limits)` adds the limit middleware. `stream_agent` is unchanged; the timeout wraps it in the runner |
| `modules/payments/runner.py:78-106` | `_run_agent` wraps in `asyncio.timeout` and maps limit errors. `_finalize` escalates with the limit explanation |
| `modules/payments/agent_state.py:16-32` | Add `limit_exceeded: AgentLimitHit \| None = None` and `precedents: list[MemoryPrecedent] = field(default_factory=list)` |
| `modules/payments/agent_tools.py:~212-240` `_register_bill` | After the claim: `state.precedents = await deps.memory.recall(owner_id, bill)`. Add `"precedents": [...]` to the tool output |
| `modules/payments/rules.py` `DecisionContext` | Add `precedents: tuple[MemoryPrecedent, ...] = ()`, which `decide()` ignores |
| `modules/payments/agent_tools.py` `_evaluate_rules` / context build | `replace(context, precedents=tuple(state.precedents))` before the checker |
| `modules/payments/checker.py:122-150` `_checker_content` | Append a `<human_precedents>` block when it isn't empty |
| `modules/prompts/payments_agent.py`, `payment_checker` prompt | Add the advisory-precedents paragraph |
| `modules/payments/dependencies.py:19-31` | Add `memory: "MemoryClient"` and `limits: AgentRunLimits` |
| `modules/payments/service.py:206-254` `approve`/`reject` | When `request.remember`, call `memory.remember_decision_later(...)` after settlement |
| `contracts/payments.py:197` `ReviewActionRequest` | Add `remember: bool = False` |
| `core/db/checkpointers.py` | Also build `AsyncPostgresStore(pool, index=...)` plus `setup()` when memory is enabled. Expose `self.store` |
| `core/db/bootstrap.py` | `CREATE EXTENSION IF NOT EXISTS vector` on the agent DB |
| `alembic/env.py:50-54` `_include_name` | Also skip `store`, `store_vectors`, `store_migrations`, `vector_migrations` |
| `container.py:85,140-152` | Build `MemoryClient(MemoryService(store, llm, embeddings?, settings.memory, registry))`, inject it into `PaymentRunDependencies`, `PaymentsService` and `DemoService` |
| `modules/demo/service.py:159` `reset` | `await memory.forget_owner(owner.user_id)` |
| `api/routers/memory.py` (new) | `GET /memories`, `DELETE /memories/{payee_key}/{memory_id}` |
| `infra/network.tf`, `compute.tf`, `ssm.tf` | Endpoint, endpoint SG, IAM invoke policy, SSM params |
| `docker-compose.yml` | `postgres-agent` image → `pgvector/pgvector:pg17` |
| `frontend/src/components/bills/ReviewActions.tsx:49-68` | "Remember this" checkbox. `api.approveBill/rejectBill(billId, note, remember)` |
| `frontend/src/app/settings/layout.tsx:8-12` + `app/settings/memories/page.tsx` (new) | New tab and page |
| `frontend/src/lib/runEvents.ts`, `components/runs/RunTimeline.tsx:135-190` | `limit_exceeded` extractor and node |

## Data Structures

### Settings (`core/config.py`)

```python
class LlmSettings(BaseSettings):            # BLINKA_LLM__
    model: str = "global.anthropic.claude-haiku-5-5"
    main_model: str | None = None
    payments_model: str | None = None
    aws_profile: str | None = None
    aws_region: str = "us-east-1"
    max_tokens: int = 8192
    timeout_s: float = 120          # botocore read_timeout
    connect_timeout_s: float = 5
    max_retries: int = 2            # botocore retries max_attempts = max_retries + 1, mode "adaptive"

class AgentSettings(BaseSettings):          # BLINKA_AGENT__
    run_timeout_s: float = Field(default=180, gt=0)
    max_tool_calls: int = Field(default=30, ge=1)
    max_model_calls: int = Field(default=35, ge=1)

class MemorySettings(BaseSettings):         # BLINKA_MEMORY__
    enabled: bool = True
    embedding_model: str = "amazon.titan-embed-text-v2:0"
    embedding_dims: int = 1024
    recall_limit: int = Field(default=5, ge=1, le=20)
    manager_query_limit: int = Field(default=10, ge=1)
    aws_profile: str | None = None      # explicit per group, like Storage/Textract/Guardrails
    aws_region: str = "us-east-1"
```

### Limits (`modules/payments/limits.py`, new)

```python
class AgentLimit(StrEnum):
    TIME = "time"
    TOOL_CALLS = "tool_calls"
    MODEL_CALLS = "model_calls"

@dataclass(frozen=True)
class AgentRunLimits:
    run_timeout_s: float
    max_tool_calls: int
    max_model_calls: int

@dataclass(frozen=True)
class AgentLimitHit:
    limit: AgentLimit
    threshold: float | int
```
Add `AgentLimitExceededError(PaymentsError)` with a `hit: AgentLimitHit` attribute to `modules/payments/errors.py`.

### Memory

**langmem schema** (`modules/memory/schemas.py`). The docstring and field descriptions **are** the extraction prompt:
```python
class PaymentPrecedent(BaseModel):
    """A reusable lesson from a finance person's decision on an escalated invoice.
    Store the generalisable rule, not the raw note. One precedent per distinct lesson."""
    payee: str = Field(description="Payee display name the lesson applies to")
    situation: str = Field(description="What made the invoice unusual, e.g. 'amount 40% above agreed'")
    human_action: Literal["approved", "rejected"]
    lesson: str = Field(description="Standalone guidance for future invoices from this payee")
    applies_when: str | None = Field(default=None, description="Conditions/limits, e.g. 'Q1 workshop invoices up to $5,000'")
```

**Stored item** (`store` table, `prefix="payments_memories.<owner_id>.<payee_key>"`, key = uuid4 str):
```json
{
  "kind": "PaymentPrecedent",
  "content": {"payee": "...", "situation": "...", "human_action": "approved", "lesson": "...", "applies_when": null},
  "source": {"bill_id": "uuid", "verdict": "pay|hold", "actor_user_id": "uuid", "note_excerpt": "≤200 chars", "decided_at": "iso8601"}
}
```
Index fields: `["content.situation", "content.lesson"]`.

**Namespace helpers** (`modules/memory/service.py`):
```python
MEMORY_NAMESPACE_ROOT = "payments_memories"
def owner_namespace(owner_id: UUID) -> tuple[str, str]: ...
def payee_namespace(owner_id: UUID, payee_key: str) -> tuple[str, str, str]: ...
def payee_key_for(payee_id: UUID | None, payee_name: str | None) -> str | None:
    # str(payee_id) | "name:" + normalize_name(payee_name) | None (no memory possible)
```

**Contracts** (`contracts/memory.py`):
```python
class DecisionMemoryInput(StrictModel):     # what PaymentsService hands to memory
    owner_id: UUID
    actor_user_id: UUID
    bill_id: UUID
    payee_id: UUID | None
    payee_name: str | None
    amount: Decimal | None
    currency: str | None
    amount_usd: Decimal | None
    category: str | None
    escalation_reasons: list[str]           # RuleResult.reason where effect is review/hold, from latest agent decision
    human_action: Literal["approved", "rejected"]
    resulting_verdict: Verdict
    note: str
    decided_at: datetime

class MemoryPrecedent(StrictModel):         # what recall returns to the agent/checker
    memory_id: str
    situation: str
    human_action: Literal["approved", "rejected"]
    lesson: str
    applies_when: str | None
    score: float | None

class MemoryView(ApiModel):                 # GET /memories row
    memory_id: str
    payee_key: str
    payee: str
    situation: str
    human_action: Literal["approved", "rejected"]
    lesson: str
    applies_when: str | None
    source_bill_id: UUID | None
    note_excerpt: str | None
    created_at: datetime
    updated_at: datetime
```

**Request change:**
```python
class ReviewActionRequest(ApiModel):
    note: str = Field(min_length=REVIEW_NOTE_MIN_LENGTH, max_length=REVIEW_NOTE_MAX_LENGTH)
    remember: bool = False
```

### Run event

`LIMIT_EXCEEDED_STEP = "limit_exceeded"`, payload `{"limit": "time"|"tool_calls"|"model_calls", "threshold": number}`. It is not terminal. A `decision_failed`/`decided` step follows (bill escalated), or `failed` if no claim existed.

Frontend type:
```ts
export type LimitExceededPayload = { limit: "time" | "tool_calls" | "model_calls"; threshold: number };
```
