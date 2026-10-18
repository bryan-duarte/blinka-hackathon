# Agent Memory Store (langmem + AsyncPostgresStore + pgvector)

## Overview

This module adds a `memory` module that stores structured `PaymentPrecedent` memories in LangGraph's `AsyncPostgresStore` inside `blinka_agent`. Memories are extracted with langmem's `create_memory_store_manager` and indexed with Bedrock Titan Embed v2 (1024 dims, pgvector).

The module exposes five operations: remember (background), recall, list, forget, forget-owner.

## Files to Modify/Create

**Infrastructure and bootstrap**
- `docker-compose.yml`: change `postgres-agent` to `image: pgvector/pgvector:pg17` (same env, ports and volume).
- `backend/core/db/bootstrap.py`: after the agent DB exists, run `CREATE EXTENSION IF NOT EXISTS vector` on it. Mirror the existing pgaudit/`CREATE DATABASE` helpers, but run it unconditionally for the agent DSN. pgvector needs no preload.
- `backend/alembic/env.py` `_include_name` (`:50-54`): also return False for `name in LANGGRAPH_STORE_TABLES = {"store", "store_vectors", "store_migrations", "vector_migrations"}`.

**Config and wiring**
- `backend/core/config.py`: add `MemorySettings` (fields in 03-design.md) and `memory: MemorySettings = Field(default_factory=MemorySettings)` on `Settings`.
- `backend/core/db/checkpointers.py`:
  - `Checkpointers.__init__(agent_dsn, pool_size, store_index: IndexConfig | None = None)`.
  - `open()` builds `AsyncPostgresStore(self._agent_pool, index=store_index)`, awaits `setup()`, and assigns `self.store`. The store is built only when `store_index is not None`; otherwise `self.store = None`.
- `backend/api/app.py` lifespan (`:120`):
  - `store_index = build_memory_index(settings.memory) if settings.memory.enabled else None`, then `Checkpointers(settings.agent_database_url, workers.checkpointer_pool_size, store_index)`.
  - On shutdown, `await clients.memory.shutdown()` next to the other worker shutdowns.
- `backend/container.py`:
  - `memory = MemoryClient(MemoryService(checkpointers.store, llm, prompts, settings.memory, ExecutionRegistry()))`.
  - Add `memory` to the `Clients` dataclass and return it.
  - Inject it into `PaymentRunDependencies` (module 07), `PaymentsService` (module 06) and `DemoService` (module 08).

**Memory module**
- `backend/modules/memory/__init__.py` (new): re-exports `MemoryService`, `build_memory_index`, errors and `__all__`.
- `backend/modules/memory/errors.py` (new): `AgentMemoryError(Exception)` and `MemoryNotFoundError(AgentMemoryError)`.
- `backend/modules/memory/schemas.py` (new): the `PaymentPrecedent` pydantic model (see 03-design.md). The docstring and descriptions are the extraction instructions.
- `backend/modules/memory/embeddings.py` (new): `build_memory_index(settings: MemorySettings) -> IndexConfig`.
- `backend/modules/memory/service.py` (new): `MemoryService` plus the namespace helpers.

**Prompts, clients and contracts**
- `backend/modules/prompts/memory_precedent.py` (new) plus a registry entry, and `PromptId.MEMORY_PRECEDENT` in `contracts/prompts.py`. This holds the manager `instructions` text, following the existing prompt-registry pattern.
- `backend/clients/memory.py` (new): `MemoryClient` with pass-through methods.
- `backend/contracts/memory.py` (new): `DecisionMemoryInput`, `MemoryPrecedent`, `MemoryView`.
- `backend/.env.example`: add `BLINKA_MEMORY__AWS_PROFILE=panoptico`, `# BLINKA_MEMORY__ENABLED=true`.

## Implementation Guidelines

```python
# orientative — memory/embeddings.py
from botocore.config import Config
from langchain_aws import BedrockEmbeddings
from langgraph.store.base import IndexConfig

PRECEDENT_INDEX_FIELDS = ["content.situation", "content.lesson"]
COSINE_DISTANCE = "cosine"

def build_memory_index(settings: MemorySettings) -> IndexConfig:
    embeddings = BedrockEmbeddings(
        model_id=settings.embedding_model,
        region_name=settings.aws_region,
        credentials_profile_name=settings.aws_profile,
        config=Config(retries={"max_attempts": 3, "mode": "adaptive"}),
    )
    return {
        "dims": settings.embedding_dims,
        "embed": embeddings,
        "fields": PRECEDENT_INDEX_FIELDS,
        "distance_type": COSINE_DISTANCE,
    }
```
- Build `AsyncPostgresStore` inside the running loop (lifespan). Its `__init__` calls `get_running_loop()`.
- The shared pool already has `autocommit=True, prepare_threshold=0, row_factory=dict_row`, which the store migrations (`CREATE INDEX CONCURRENTLY`) require.

```python
# orientative — memory/service.py
from langmem import create_memory_store_manager
from langmem.errors import ConfigurationError

MEMORY_NAMESPACE_ROOT = "payments_memories"
PRECEDENT_KIND = "PaymentPrecedent"
NAME_KEY_PREFIX = "name:"
NOTE_EXCERPT_CHARS = 200
MEMORY_MODEL_KIND: ModelKind = "main"
OWNER_LIST_LIMIT = 200
PURGE_BATCH_SIZE = 100

def payee_key_for(payee_id: UUID | None, payee_name: str | None) -> str | None:
    if payee_id is not None:
        return str(payee_id)
    normalized = normalize_name(payee_name) if payee_name else ""
    return f"{NAME_KEY_PREFIX}{normalized}" if normalized else None

def owner_namespace(owner_id: UUID) -> tuple[str, ...]:
    return (MEMORY_NAMESPACE_ROOT, str(owner_id))

def payee_namespace(owner_id: UUID, payee_key: str) -> tuple[str, ...]:
    return (*owner_namespace(owner_id), payee_key)


class MemoryService:
    def __init__(self, store, llm, prompts, settings, registry) -> None:
        self._store = store
        self._settings = settings
        self._registry = registry
        self._manager = (
            create_memory_store_manager(
                llm.model(MEMORY_MODEL_KIND),
                schemas=[PaymentPrecedent],
                instructions=prompts.get_text_prompt(PromptId.MEMORY_PRECEDENT),
                enable_inserts=True,
                enable_deletes=False,
                query_limit=settings.manager_query_limit,
                namespace=(MEMORY_NAMESPACE_ROOT, "{owner_id}", "{payee_key}"),
                store=store,
            )
            if store is not None
            else None
        )

    def remember_decision_later(self, memory_input: DecisionMemoryInput) -> None:
        if self._manager is None:
            return
        self._registry.spawn(uuid4(), self._remember_safely(memory_input), owner_id=memory_input.owner_id)

    async def _remember_safely(self, memory_input: DecisionMemoryInput) -> None:
        try:
            count = await self.remember_decision(memory_input)
            logger.info("memory_extracted", bill_id=memory_input.bill_id, count=count)
        except (Exception, ConfigurationError):          # ConfigurationError is a BaseException
            logger.exception("memory_extraction_failed", bill_id=memory_input.bill_id)

    async def remember_decision(self, memory_input: DecisionMemoryInput) -> int:
        payee_key = payee_key_for(memory_input.payee_id, memory_input.payee_name)
        if payee_key is None:
            logger.info("memory_skipped_no_payee", bill_id=memory_input.bill_id)
            return 0
        config = {"configurable": {"owner_id": str(memory_input.owner_id), "payee_key": payee_key}}
        puts = await self._manager.ainvoke({"messages": [HumanMessage(content=_decision_transcript(memory_input))]}, config=config)
        source = _source(memory_input)
        for put in puts:
            await self._store.aput(tuple(put["namespace"]), put["key"], {**put["value"], "source": source})
        return len(puts)

    async def recall(self, owner_id: UUID, payee_id: UUID | None, payee_name: str | None, query: str) -> list[MemoryPrecedent]:
        payee_key = payee_key_for(payee_id, payee_name)
        if self._store is None or payee_key is None:
            return []
        items = await self._store.asearch(payee_namespace(owner_id, payee_key), query=query, limit=self._settings.recall_limit)
        return [_to_precedent(item) for item in items if item.value.get("kind") == PRECEDENT_KIND]

    async def list_for_owner(self, owner_id: UUID) -> list[MemoryView]: ...      # asearch(owner_namespace, limit=OWNER_LIST_LIMIT), no query → updated_at desc
    async def forget(self, owner_id: UUID, payee_key: str, memory_id: str) -> None: ...  # aget → None ⇒ MemoryNotFoundError; else adelete
    async def forget_owner(self, owner_id: UUID) -> int: ...  # loop asearch(owner_namespace, limit=PURGE_BATCH_SIZE) + adelete until empty
    async def cancel_owner(self, owner_id: UUID) -> int: return await self._registry.cancel_owner(owner_id)
    async def shutdown(self) -> None: await self._registry.shutdown()
```

**Manager return value.** Verify what `MemoryStoreManager.ainvoke` returns in langmem 0.0.30: a list of put dicts with `namespace`, `key` and `value`. Adapt the enrichment loop to the actual shape. If it returns only keys, `aget` each one first.

**Re-put after extraction.** Re-putting with the extra top-level `"source"` re-embeds only the indexed fields. That costs one Titan call per memory, which is acceptable. langmem reads only `value["kind"]` and `value["content"]`, so the extra key is safe.

**Transcript passed to langmem.** Built by `_decision_transcript`, using tagged sections so the model can tell data from instructions:

```
<invoice payee="..." amount="..." currency="..." amount_usd="..." category="..."/>
<why_escalated>- reason 1\n- reason 2</why_escalated>
<human_action>approved|rejected</human_action>
<human_note>...</human_note>
```

**`MEMORY_PRECEDENT` prompt (instructions).** Extract only reusable lessons a finance person would want applied to future invoices from this payee. Don't copy the note verbatim. Skip notes with no reusable content. Update an existing precedent instead of duplicating it. Never record amounts as permanent approvals beyond what the note states.

**`_to_precedent` / `_to_view`.** Map `item.key` to `memory_id`, `item.value["content"][...]`, `item.score`, `item.created_at` and `item.updated_at`. The view's `payee_key` is `item.namespace[2]`.

**Disabled mode.** With `store is None`:
- `recall` and `list_for_owner` return `[]`.
- `remember_decision_later` is a no-op.
- `forget` raises `MemoryNotFoundError`.
- `forget_owner` returns 0.

## Dependencies

- `langmem` and `langchain-aws`, both added in module 02.
- `langgraph.store.postgres.AsyncPostgresStore`, from langgraph-checkpoint-postgres 3.2.0, already installed.
- `modules.payment_policy` `normalize_name`. Import it through its public `__init__` if it is exported there; otherwise use `modules.payment_policy.normalize`.
- `core.background.ExecutionRegistry`.

## Integration Notes

- `MemoryClient` methods:
  - `remember_decision_later(DecisionMemoryInput) -> None`
  - `recall(owner_id, payee_id, payee_name, query) -> list[MemoryPrecedent]`
  - `list_for_owner(owner_id) -> list[MemoryView]`
  - `forget(owner_id, payee_key, memory_id) -> None`
  - `forget_owner(owner_id) -> int`
  - `cancel_owner(owner_id) -> int`
  - `shutdown() -> None`
- Prefix matching: `asearch(("payments_memories", owner_id))` also returns every payee sub-namespace. `list_for_owner` and `forget_owner` rely on this.
- Store tables live only in `blinka_agent`. Product DB migrations are untouched.
