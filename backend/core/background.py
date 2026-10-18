import asyncio
from collections.abc import Coroutine
from functools import partial
from uuid import UUID

from core.logging_config import get_logger

logger = get_logger(__name__)


class ExecutionRegistry:
    def __init__(self) -> None:
        self._tasks: dict[UUID, asyncio.Task[None]] = {}
        self._owners: dict[UUID, UUID] = {}

    def spawn(
        self,
        task_id: UUID,
        execution: Coroutine[object, object, None],
        owner_id: UUID | None = None,
    ) -> asyncio.Task[None]:
        task = asyncio.create_task(execution)
        self._tasks[task_id] = task
        if owner_id is not None:
            self._owners[task_id] = owner_id
        task.add_done_callback(partial(self._reap, task_id))
        return task

    async def cancel_owner(self, owner_id: UUID) -> int:
        owned_tasks = [
            task for task_id, task in self._tasks.items() if self._owners.get(task_id) == owner_id
        ]
        for task in owned_tasks:
            task.cancel()
        await asyncio.gather(*owned_tasks, return_exceptions=True)
        return len(owned_tasks)

    def _reap(self, task_id: UUID, task: asyncio.Task[None]) -> None:
        self._tasks.pop(task_id, None)
        self._owners.pop(task_id, None)
        if task.cancelled():
            return
        task_error = task.exception()
        if task_error is not None:
            logger.error("background_task_crashed", task_id=task_id, exc_info=task_error)

    async def shutdown(self) -> None:
        for task in self._tasks.values():
            task.cancel()
        await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        self._tasks.clear()
        self._owners.clear()
