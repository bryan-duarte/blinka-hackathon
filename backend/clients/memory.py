from typing import TYPE_CHECKING
from uuid import UUID

from contracts.memory import DecisionMemoryInput, MemoryPrecedent, MemoryView

if TYPE_CHECKING:
    from modules.memory.service import MemoryService


class MemoryClient:
    def __init__(self, service: "MemoryService") -> None:
        self._service = service

    def remember_decision_later(self, memory_input: DecisionMemoryInput) -> None:
        self._service.remember_decision_later(memory_input)

    async def recall(
        self, owner_id: UUID, payee_id: UUID | None, payee_name: str | None, query: str
    ) -> list[MemoryPrecedent]:
        return await self._service.recall(owner_id, payee_id, payee_name, query)

    async def list_for_owner(self, owner_id: UUID) -> list[MemoryView]:
        return await self._service.list_for_owner(owner_id)

    async def forget(self, owner_id: UUID, payee_key: str, memory_id: str) -> None:
        await self._service.forget(owner_id, payee_key, memory_id)

    async def forget_owner(self, owner_id: UUID) -> int:
        return await self._service.forget_owner(owner_id)

    async def cancel_owner(self, owner_id: UUID) -> int:
        return await self._service.cancel_owner(owner_id)

    async def shutdown(self) -> None:
        await self._service.shutdown()
