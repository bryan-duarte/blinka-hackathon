from fastapi import APIRouter, status

from api.deps import ClientsDep, CurrentUserDep
from contracts.memory import MemoryView

memory_router = APIRouter(prefix="/memories", tags=["memory"])


@memory_router.get("", response_model=list[MemoryView])
async def list_memories(user: CurrentUserDep, clients: ClientsDep) -> list[MemoryView]:
    return await clients.memory.list_for_owner(user.user_id)


@memory_router.delete("/{payee_key}/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    payee_key: str, memory_id: str, user: CurrentUserDep, clients: ClientsDep
) -> None:
    await clients.memory.forget(user.user_id, payee_key, memory_id)
