import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from contracts.auth import CurrentUser
from contracts.demo import DemoExpectation, DemoLaunchStatus, DemoLaunchStepView, DemoLaunchView
from contracts.inbox import InboxEmailStatus
from core.logging_config import get_logger
from modules.demo.catalog import DemoScenario, LaunchContext, as_whatsapp_message

if TYPE_CHECKING:
    from clients.inbox import InboxClient

logger = get_logger(__name__)

TERMINAL_INBOX_STATUSES = frozenset(
    {
        InboxEmailStatus.BLOCKED,
        InboxEmailStatus.PAID,
        InboxEmailStatus.HELD,
        InboxEmailStatus.REVIEW,
        InboxEmailStatus.DUPLICATE,
        InboxEmailStatus.NO_INVOICE,
        InboxEmailStatus.NO_INFO,
        InboxEmailStatus.ERROR,
    }
)
SEQUENCE_POLL_SECONDS = 1.0
STEP_TIMEOUT_SECONDS = 900
STEP_TIMEOUT_ERROR = "step did not finish in time"
UNEXPECTED_ERROR = "unexpected error"


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass
class LaunchStep:
    expected: DemoExpectation
    email_id: UUID | None = None
    status: InboxEmailStatus | None = None

    @property
    def is_as_expected(self) -> bool | None:
        if self.status is None or self.status not in TERMINAL_INBOX_STATUSES:
            return None
        return self.status == self.expected.outcome


@dataclass
class DemoLaunch:
    launch_id: UUID
    owner_id: UUID
    scenario_id: str
    steps: list[LaunchStep]
    started_at: datetime = field(default_factory=_utc_now)
    status: DemoLaunchStatus = DemoLaunchStatus.RUNNING
    error: str | None = None

    @property
    def is_running(self) -> bool:
        return self.status is DemoLaunchStatus.RUNNING

    def mark_injected(self, index: int, email_id: UUID) -> None:
        self.steps[index].email_id = email_id
        self.steps[index].status = InboxEmailStatus.RECEIVED

    def mark_status(self, index: int, status: InboxEmailStatus) -> None:
        self.steps[index].status = status

    def fail(self, error: str) -> None:
        self.status = DemoLaunchStatus.FAILED
        self.error = error

    def to_view(self) -> DemoLaunchView:
        return DemoLaunchView(
            launch_id=self.launch_id,
            scenario_id=self.scenario_id,
            status=self.status,
            steps=[
                DemoLaunchStepView(
                    index=index,
                    email_id=step.email_id,
                    status=step.status,
                    expected=step.expected,
                    is_as_expected=step.is_as_expected,
                )
                for index, step in enumerate(self.steps)
            ],
            started_at=self.started_at,
            error=self.error,
        )


async def run_sequence(
    launch: DemoLaunch,
    scenario: DemoScenario,
    owner: CurrentUser,
    inbox: "InboxClient",
    context: LaunchContext,
) -> None:
    try:
        for index, step in enumerate(scenario.steps):
            message = await asyncio.to_thread(step.build, context)
            if scenario.channel == "whatsapp":
                message = as_whatsapp_message(message)
            injected = await inbox.inject(owner, message, scenario.channel)
            launch.mark_injected(index, injected.email_id)
            await _wait_terminal(launch, index, inbox, owner, injected.email_id)
        launch.status = DemoLaunchStatus.COMPLETED
        logger.info("demo_sequence_completed", launch_id=launch.launch_id)
    except asyncio.CancelledError:
        launch.status = DemoLaunchStatus.CANCELLED
        raise
    except TimeoutError:
        logger.warning("demo_sequence_timed_out", launch_id=launch.launch_id)
        launch.fail(STEP_TIMEOUT_ERROR)
    except Exception:
        logger.exception("demo_sequence_failed", launch_id=launch.launch_id)
        launch.fail(UNEXPECTED_ERROR)


async def _wait_terminal(
    launch: DemoLaunch,
    index: int,
    inbox: "InboxClient",
    owner: CurrentUser,
    email_id: UUID,
) -> None:
    async with asyncio.timeout(STEP_TIMEOUT_SECONDS):
        while True:
            status = await inbox.get_email_status(owner, email_id)
            launch.mark_status(index, status)
            if status in TERMINAL_INBOX_STATUSES:
                return
            await asyncio.sleep(SEQUENCE_POLL_SECONDS)
