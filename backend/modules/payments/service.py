from typing import TYPE_CHECKING
from uuid import UUID

from contracts.auth import CurrentUser
from contracts.payments import (
    PaymentRunAccepted,
    PaymentRunStatus,
    PaymentRunTrigger,
    RunStatus,
)
from core.logging_config import get_logger
from modules.payments.agent import PAYMENTS_AGENT_NAME
from modules.payments.errors import RunNotFoundError
from modules.payments.repository import RunsRepository
from modules.payments.runner import ExecutionRegistry, PaymentRunDependencies, run_execution

logger = get_logger(__name__)

if TYPE_CHECKING:
    from clients.files import FilesClient


class PaymentsService:
    def __init__(
        self,
        repository: RunsRepository,
        registry: ExecutionRegistry,
        dependencies: PaymentRunDependencies,
        files: "FilesClient",
    ) -> None:
        self._repository = repository
        self._registry = registry
        self._dependencies = dependencies
        self._files = files

    async def start_run(self, trigger: PaymentRunTrigger, owner: CurrentUser) -> PaymentRunAccepted:
        await self._files.get(owner, trigger.file_id)
        run_id = await self._repository.insert_run(
            agent=PAYMENTS_AGENT_NAME,
            owner_id=owner.user_id,
            file_id=trigger.file_id,
            session_id=trigger.session_id,
        )
        self._registry.spawn(
            run_id,
            run_execution(run_id, owner, trigger.file_id, trigger.session_id, self._dependencies),
        )
        logger.info("payment_run_started", run_id=run_id, file_id=trigger.file_id)
        return PaymentRunAccepted(run_id=run_id, status=RunStatus.PENDING)

    async def get_run(self, run_id: UUID, owner: CurrentUser) -> PaymentRunStatus:
        run = await self._repository.get_run(run_id, owner.user_id)
        if run is None:
            raise RunNotFoundError
        events = await self._repository.list_events(run_id)
        return PaymentRunStatus(
            run_id=run.run_id, status=run.status, error=run.error, events=events
        )

    async def fail_unfinished(self, reason: str) -> None:
        failed_count = await self._repository.fail_unfinished(reason)
        if failed_count:
            logger.warning("unfinished_runs_swept", failed_count=failed_count)

    async def shutdown(self) -> None:
        await self._registry.shutdown()
