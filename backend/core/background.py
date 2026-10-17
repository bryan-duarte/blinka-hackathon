import asyncio
from collections.abc import Coroutine
from functools import partial
from uuid import UUID

from core.logging_config import get_logger

logger = get_logger(__name__)


class ExecutionRegistry:
    def __init__(self) -> None:
        self._tasks: dict[UUID, asyncio.Task[None]] = {}

    def spawn(self, task_id: UUID, execution: Coroutine[object, object, None]) -> None:
        task = asyncio.create_task(execution)
        self._tasks[task_id] = task
        task.add_done_callback(partial(self._reap, task_id))

    def _reap(self, task_id: UUID, task: asyncio.Task[None]) -> None:
        self._tasks.pop(task_id, None)
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
