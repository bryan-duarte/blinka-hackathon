from html import escape
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from langchain_core.messages import HumanMessage
from langgraph.store.base import BaseStore, Item, SearchItem
from langmem import create_memory_store_manager
from langmem.errors import ConfigurationError
from pydantic import ValidationError

from contracts.llm import ModelKind
from contracts.memory import DecisionMemoryInput, MemoryPrecedent, MemoryView
from contracts.prompts import PromptId
from core.background import ExecutionRegistry
from core.config import MemorySettings
from core.logging_config import get_logger
from modules.memory.errors import MemoryNotFoundError
from modules.memory.schemas import PaymentPrecedent, PrecedentSource
from modules.payment_policy import normalize_name

if TYPE_CHECKING:
    from clients.llm import LlmGatewayClient
    from clients.prompts import PromptsClient

logger = get_logger(__name__)

MEMORY_NAMESPACE_ROOT = "payments_memories"
OWNER_TEMPLATE = "{owner_id}"
PAYEE_KEY_TEMPLATE = "{payee_key}"
PRECEDENT_KIND = PaymentPrecedent.__name__
NAME_KEY_PREFIX = "name:"
NOTE_EXCERPT_CHARS = 200
MEMORY_MODEL_KIND: ModelKind = "main"
OWNER_LIST_LIMIT = 200
PURGE_BATCH_SIZE = 100
PAYEE_KEY_NAMESPACE_INDEX = 2
UNKNOWN_FIELD = "unknown"
NAMESPACE_LABEL_SEPARATOR = "."
STORED_KIND_FIELD = "kind"
STORED_CONTENT_FIELD = "content"
STORED_SOURCE_FIELD = "source"


def payee_key_for(payee_id: UUID | None, payee_name: str | None) -> str | None:
    if payee_id is not None:
        return str(payee_id)
    normalized_name = normalize_name(payee_name) if payee_name else ""
    return f"{NAME_KEY_PREFIX}{normalized_name}" if normalized_name else None


def owner_namespace(owner_id: UUID) -> tuple[str, ...]:
    return (MEMORY_NAMESPACE_ROOT, str(owner_id))


def payee_namespace(owner_id: UUID, payee_key: str) -> tuple[str, ...]:
    return (*owner_namespace(owner_id), payee_key)


class MemoryService:
    def __init__(
        self,
        store: BaseStore | None,
        llm: "LlmGatewayClient",
        prompts: "PromptsClient",
        settings: MemorySettings,
        registry: ExecutionRegistry,
    ) -> None:
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
                namespace=(MEMORY_NAMESPACE_ROOT, OWNER_TEMPLATE, PAYEE_KEY_TEMPLATE),
                store=store,
            )
            if store is not None
            else None
        )

    def remember_decision_later(self, memory_input: DecisionMemoryInput) -> None:
        if self._manager is None:
            return
        self._registry.spawn(
            uuid4(), self._remember_safely(memory_input), owner_id=memory_input.owner_id
        )

    async def remember_decision(self, memory_input: DecisionMemoryInput) -> int:
        if self._manager is None or self._store is None:
            return 0
        payee_key = payee_key_for(memory_input.payee_id, memory_input.payee_name)
        if payee_key is None:
            logger.info("memory_skipped_no_payee", bill_id=memory_input.bill_id)
            return 0
        manager_config = {
            "configurable": {"owner_id": str(memory_input.owner_id), "payee_key": payee_key}
        }
        transcript = HumanMessage(content=_decision_transcript(memory_input))
        memory_puts = await self._manager.ainvoke({"messages": [transcript]}, config=manager_config)
        source = _precedent_source(memory_input).model_dump(mode="json")
        for memory_put in memory_puts:
            await self._store.aput(
                tuple(memory_put["namespace"]),
                memory_put["key"],
                {**memory_put["value"], STORED_SOURCE_FIELD: source},
            )
        return len(memory_puts)

    async def recall(
        self, owner_id: UUID, payee_id: UUID | None, payee_name: str | None, query: str
    ) -> list[MemoryPrecedent]:
        payee_key = payee_key_for(payee_id, payee_name)
        if self._store is None or payee_key is None:
            return []
        stored_memories = await self._store.asearch(
            payee_namespace(owner_id, payee_key), query=query, limit=self._settings.recall_limit
        )
        return [
            precedent
            for stored_memory in stored_memories
            if (precedent := _to_precedent(stored_memory)) is not None
        ]

    async def list_for_owner(self, owner_id: UUID) -> list[MemoryView]:
        if self._store is None:
            return []
        stored_memories = await self._store.asearch(
            owner_namespace(owner_id), limit=OWNER_LIST_LIMIT
        )
        return [
            view
            for stored_memory in stored_memories
            if (view := _to_view(stored_memory)) is not None
        ]

    async def forget(self, owner_id: UUID, payee_key: str, memory_id: str) -> None:
        is_valid_payee_key = bool(payee_key) and NAMESPACE_LABEL_SEPARATOR not in payee_key
        if self._store is None or not is_valid_payee_key:
            raise MemoryNotFoundError(memory_id)
        namespace = payee_namespace(owner_id, payee_key)
        stored_memory = await self._store.aget(namespace, memory_id)
        if stored_memory is None:
            raise MemoryNotFoundError(memory_id)
        await self._store.adelete(namespace, memory_id)

    async def forget_owner(self, owner_id: UUID) -> int:
        if self._store is None:
            return 0
        deleted_count = 0
        while stored_memories := await self._store.asearch(
            owner_namespace(owner_id), limit=PURGE_BATCH_SIZE
        ):
            for stored_memory in stored_memories:
                await self._store.adelete(stored_memory.namespace, stored_memory.key)
            deleted_count += len(stored_memories)
        return deleted_count

    async def cancel_owner(self, owner_id: UUID) -> int:
        return await self._registry.cancel_owner(owner_id)

    async def shutdown(self) -> None:
        await self._registry.shutdown()

    async def _remember_safely(self, memory_input: DecisionMemoryInput) -> None:
        try:
            memory_count = await self.remember_decision(memory_input)
        except (Exception, ConfigurationError):
            logger.exception("memory_extraction_failed", bill_id=memory_input.bill_id)
            return
        logger.info("memory_extracted", bill_id=memory_input.bill_id, count=memory_count)


def _decision_transcript(memory_input: DecisionMemoryInput) -> str:
    invoice_attributes = " ".join(
        f'{name}="{_attribute_text(attribute_value)}"'
        for name, attribute_value in (
            ("payee", memory_input.payee_name),
            ("amount", memory_input.amount),
            ("currency", memory_input.currency),
            ("amount_usd", memory_input.amount_usd),
            ("category", memory_input.category),
        )
    )
    escalation_lines = "\n".join(
        f"- {escape(reason)}" for reason in memory_input.escalation_reasons
    )
    return (
        f"<invoice {invoice_attributes}/>\n"
        f"<why_escalated>\n{escalation_lines}\n</why_escalated>\n"
        f"<human_action>{memory_input.human_action}</human_action>\n"
        f"<human_note>{escape(memory_input.note)}</human_note>"
    )


def _attribute_text(attribute_value: object | None) -> str:
    return escape(UNKNOWN_FIELD if attribute_value is None else str(attribute_value))


def _precedent_source(memory_input: DecisionMemoryInput) -> PrecedentSource:
    return PrecedentSource(
        bill_id=memory_input.bill_id,
        verdict=memory_input.resulting_verdict,
        actor_user_id=memory_input.actor_user_id,
        note_excerpt=memory_input.note[:NOTE_EXCERPT_CHARS],
        decided_at=memory_input.decided_at,
    )


def _stored_precedent(stored_memory: Item) -> PaymentPrecedent | None:
    is_precedent = stored_memory.value.get(STORED_KIND_FIELD) == PRECEDENT_KIND
    if not is_precedent:
        return None
    try:
        return PaymentPrecedent.model_validate(stored_memory.value.get(STORED_CONTENT_FIELD))
    except ValidationError:
        logger.warning("memory_item_invalid", memory_id=stored_memory.key)
        return None


def _stored_source(stored_memory: Item) -> PrecedentSource | None:
    try:
        return PrecedentSource.model_validate(stored_memory.value.get(STORED_SOURCE_FIELD))
    except ValidationError:
        return None


def _to_precedent(stored_memory: SearchItem) -> MemoryPrecedent | None:
    precedent = _stored_precedent(stored_memory)
    if precedent is None:
        return None
    source = _stored_source(stored_memory)
    return MemoryPrecedent(
        memory_id=stored_memory.key,
        situation=precedent.situation,
        human_action=precedent.human_action,
        lesson=precedent.lesson,
        applies_when=precedent.applies_when,
        decided_at=source.decided_at if source else None,
        score=stored_memory.score,
    )


def _to_view(stored_memory: SearchItem) -> MemoryView | None:
    precedent = _stored_precedent(stored_memory)
    if precedent is None:
        return None
    source = _stored_source(stored_memory)
    return MemoryView(
        memory_id=stored_memory.key,
        payee_key=stored_memory.namespace[PAYEE_KEY_NAMESPACE_INDEX],
        payee=precedent.payee,
        situation=precedent.situation,
        human_action=precedent.human_action,
        lesson=precedent.lesson,
        applies_when=precedent.applies_when,
        source_bill_id=source.bill_id if source else None,
        note_excerpt=source.note_excerpt if source else None,
        created_at=stored_memory.created_at,
        updated_at=stored_memory.updated_at,
    )
