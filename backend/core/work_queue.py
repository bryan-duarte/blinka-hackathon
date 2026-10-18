import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from core.background import ExecutionRegistry
from core.logging_config import get_logger

logger = get_logger(__name__)


class QueuedWork(Protocol):
    @property
    def owner_id(self) -> UUID: ...


@dataclass(frozen=True)
class QueueLimits:
    concurrency: int
    poll_interval_seconds: float


class QueueWorker[WorkT: QueuedWork]:
    def __init__(
        self,
        name: str,
        claim: Callable[[int], Awaitable[list[WorkT]]],
        handle: Callable[[WorkT], Awaitable[None]],
        work_id: Callable[[WorkT], UUID],
        registry: ExecutionRegistry,
        limits: QueueLimits,
    ) -> None:
        self._name = name
        self._claim = claim
        self._handle = handle
        self._work_id = work_id
        self._registry = registry
        self._limits = limits
        self._in_flight = 0
        self._wake = asyncio.Event()
        self._loop_task: asyncio.Task[None] | None = None

    def notify(self) -> None:
        self._wake.set()

    def start(self) -> None:
        self._loop_task = asyncio.create_task(self._run_loop())
        self._loop_task.add_done_callback(self._report_loop_exit)
        logger.info("queue_worker_started", queue=self._name, concurrency=self._limits.concurrency)

    async def stop(self) -> None:
        if self._loop_task is None:
            return
        self._loop_task.cancel()
        await asyncio.gather(self._loop_task, return_exceptions=True)
        self._loop_task = None

    async def _run_loop(self) -> None:
        while True:
            self._wake.clear()
            claimed_work = await self._claim_free_slots()
            for work in claimed_work:
                self._dispatch(work)
            if not claimed_work:
                await self._wait_for_wake()

    async def _claim_free_slots(self) -> list[WorkT]:
        free_slots = self._limits.concurrency - self._in_flight
        if free_slots <= 0:
            return []
        try:
            claimed_work = await self._claim(free_slots)
        except Exception:
            logger.exception("queue_claim_failed", queue=self._name)
            return []
        if claimed_work:
            logger.info("queue_claimed", queue=self._name, count=len(claimed_work))
        has_backlog = len(claimed_work) == free_slots
        if has_backlog:
            logger.info(
                "queue_backlog_waiting", queue=self._name, in_flight=self._limits.concurrency
            )
        return claimed_work

    def _dispatch(self, work: WorkT) -> None:
        self._in_flight += 1
        task = self._registry.spawn(self._work_id(work), self._handle(work), owner_id=work.owner_id)
        task.add_done_callback(self._release_slot)

    def _release_slot(self, task: asyncio.Task[None]) -> None:
        self._in_flight -= 1
        self._wake.set()

    def _report_loop_exit(self, loop_task: asyncio.Task[None]) -> None:
        if loop_task.cancelled():
            return
        logger.error("queue_worker_died", queue=self._name, exc_info=loop_task.exception())

    async def _wait_for_wake(self) -> None:
        try:
            async with asyncio.timeout(self._limits.poll_interval_seconds):
                await self._wake.wait()
        except TimeoutError:
            return
