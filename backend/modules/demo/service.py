import asyncio
import secrets
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from contracts.auth import CurrentUser
from contracts.demo import (
    DemoCatalogView,
    DemoLaunchView,
    DemoResetResult,
    KitDestinations,
)
from contracts.realtime import RealtimeEvent, RealtimeEventType
from core.background import ExecutionRegistry
from core.config import DemoSettings
from core.logging_config import get_logger
from modules.demo.catalog import (
    DEMO_SCENARIOS,
    MALWARE_SCENARIO_ID,
    SCENARIOS_BY_ID,
    DemoScenario,
    LaunchContext,
    expected_outcome,
    section_views,
)
from modules.demo.errors import (
    DemoBusyError,
    DemoDisabledError,
    DemoLaunchLimitError,
    DemoLaunchMissingError,
    DemoResetFailedError,
    DemoScenarioMissingError,
    DemoScenarioUnavailableError,
)
from modules.demo.kit import build_kit_zip
from modules.demo.reset_repository import DemoResetRepository
from modules.demo.seeder import DemoSeeder
from modules.demo.sequencer import DemoLaunch, LaunchStep, run_sequence
from modules.files import StorageError
from modules.payment_policy import PolicyMissingError

if TYPE_CHECKING:
    from clients.auth import AuthClient
    from clients.files import FilesClient
    from clients.inbox import InboxClient
    from clients.memory import MemoryClient
    from clients.payment_policy import PaymentPolicyClient
    from clients.payments import PaymentsClient
    from clients.realtime import RealtimeClient

logger = get_logger(__name__)

LAUNCH_NONCE_MIN = 100_000
LAUNCH_NONCE_SPAN = 900_000
MAX_LAUNCHES_PER_OWNER = 50
RESET_EVENT_STATUS = "reset"


class DemoService:
    def __init__(
        self,
        settings: DemoSettings,
        auth: "AuthClient",
        policy: "PaymentPolicyClient",
        inbox: "InboxClient",
        payments: "PaymentsClient",
        files: "FilesClient",
        realtime: "RealtimeClient",
        memory: "MemoryClient",
        seeder: DemoSeeder,
        reset_repository: DemoResetRepository,
        registry: ExecutionRegistry,
        destinations: KitDestinations,
        is_guardrail_enforced: bool,
        is_malware_scan_enabled: bool,
    ) -> None:
        self._settings = settings
        self._auth = auth
        self._policy = policy
        self._inbox = inbox
        self._payments = payments
        self._files = files
        self._realtime = realtime
        self._memory = memory
        self._seeder = seeder
        self._reset_repository = reset_repository
        self._registry = registry
        self._destinations = destinations
        self._is_guardrail_enforced = is_guardrail_enforced
        self._is_malware_scan_enabled = is_malware_scan_enabled
        self._launches: dict[UUID, DemoLaunch] = {}
        self._lock = asyncio.Lock()

    async def ensure_demo_account(self) -> CurrentUser:
        password = self._settings.password
        if password is None:
            raise DemoDisabledError
        owner = await self._auth.ensure_user_with_password(
            self._settings.email, password.get_secret_value()
        )
        try:
            await self._policy.get_policy(owner)
        except PolicyMissingError:
            await self._seeder.seed(owner)
        return owner

    def catalog(self) -> DemoCatalogView:
        return DemoCatalogView(
            company_name=self._settings.company_name,
            sections=section_views(self._destinations, self._is_guardrail_enforced),
            is_guardrail_enforced=self._is_guardrail_enforced,
            is_malware_scan_enabled=self._is_malware_scan_enabled,
            destinations=self._destinations,
        )

    def launch(self, owner: CurrentUser, scenario_id: str) -> DemoLaunchView:
        if self._lock.locked():
            raise DemoBusyError
        scenario = _require_scenario(scenario_id)
        is_malware_scan_off = (
            scenario_id == MALWARE_SCENARIO_ID and not self._is_malware_scan_enabled
        )
        if is_malware_scan_off:
            raise DemoScenarioUnavailableError
        running_count = sum(
            1
            for launch in self._launches.values()
            if launch.owner_id == owner.user_id and launch.is_running
        )
        if running_count >= self._settings.max_running_launches:
            raise DemoLaunchLimitError
        context = LaunchContext(
            today=datetime.now(UTC).date(),
            nonce=secrets.randbelow(LAUNCH_NONCE_SPAN) + LAUNCH_NONCE_MIN,
        )
        launch = DemoLaunch(
            launch_id=uuid4(),
            owner_id=owner.user_id,
            scenario_id=scenario_id,
            steps=[
                LaunchStep(expected=expected_outcome(step, self._is_guardrail_enforced))
                for step in scenario.steps
            ],
        )
        self._forget_old_launches(owner.user_id)
        self._launches[launch.launch_id] = launch
        self._registry.spawn(
            launch.launch_id,
            run_sequence(launch, scenario, owner, self._inbox, context),
            owner_id=owner.user_id,
        )
        logger.info("demo_scenario_launched", launch_id=launch.launch_id, scenario_id=scenario_id)
        return launch.to_view()

    def get_launch(self, owner: CurrentUser, launch_id: UUID) -> DemoLaunchView:
        launch = self._launches.get(launch_id)
        if launch is None or launch.owner_id != owner.user_id:
            raise DemoLaunchMissingError
        return launch.to_view()

    async def reset(self, owner: CurrentUser) -> DemoResetResult:
        if self._lock.locked():
            raise DemoBusyError
        async with self._lock:
            await self._registry.cancel_owner(owner.user_id)
            self._forget_launches(owner.user_id)
            await self._cancel_pipelines(owner.user_id)
            owner_refs = await self._reset_repository.collect_owner_refs(owner.user_id)
            try:
                deleted_rows = await self._reset_repository.purge_owner(owner.user_id)
            except Exception as purge_error:
                logger.exception("demo_reset_purge_failed", owner_id=owner.user_id)
                raise DemoResetFailedError from purge_error
            deleted_objects = await self._purge_objects(owner, owner_refs.stored_file_count)
            await self._payments.purge_run_threads(owner_refs.run_ids)
            await self._cancel_pipelines(owner.user_id)
            try:
                deleted_memories = await self._memory.forget_owner(owner.user_id)
            except Exception as memory_error:
                logger.exception("demo_reset_memory_purge_failed", owner_id=owner.user_id)
                raise DemoResetFailedError from memory_error
            try:
                seeded_bills = await self._seeder.seed(owner)
            except Exception as seed_error:
                logger.exception("demo_reset_seed_failed", owner_id=owner.user_id)
                raise DemoResetFailedError from seed_error
            await self._publish_reset(owner)
        logger.info(
            "demo_reset_completed",
            owner_id=owner.user_id,
            deleted_rows=deleted_rows,
            deleted_objects=deleted_objects,
            deleted_memories=deleted_memories,
        )
        return DemoResetResult(
            deleted_rows=deleted_rows,
            deleted_objects=deleted_objects,
            seeded_bills=seeded_bills,
            reset_at=datetime.now(UTC),
        )

    async def scenario_kit(self, scenario_id: str) -> bytes:
        scenario = _require_scenario(scenario_id)
        return await asyncio.to_thread(self._kit, [scenario])

    async def full_kit(self) -> bytes:
        return await asyncio.to_thread(self._kit, list(DEMO_SCENARIOS))

    async def shutdown(self) -> None:
        await self._registry.shutdown()

    def _kit(self, scenarios: list[DemoScenario]) -> bytes:
        return build_kit_zip(
            scenarios, datetime.now(UTC).date(), self._destinations, self._is_guardrail_enforced
        )

    async def _cancel_pipelines(self, owner_id: UUID) -> None:
        await self._inbox.cancel_owner(owner_id)
        await self._payments.cancel_owner(owner_id)
        await self._memory.cancel_owner(owner_id)

    async def _purge_objects(self, owner: CurrentUser, stored_file_count: int) -> int:
        if stored_file_count == 0:
            return 0
        try:
            return await self._files.purge_owner_objects(owner.user_id)
        except StorageError:
            logger.warning("demo_reset_storage_purge_failed", owner_id=owner.user_id, exc_info=True)
            return 0

    async def _publish_reset(self, owner: CurrentUser) -> None:
        await self._realtime.publish(
            owner.user_id,
            [
                RealtimeEvent(
                    type=RealtimeEventType.INBOX_ITEM,
                    item_id=None,
                    step=RESET_EVENT_STATUS,
                    payload={"status": RESET_EVENT_STATUS},
                    created_at=datetime.now(UTC),
                )
            ],
        )

    def _forget_launches(self, owner_id: UUID) -> None:
        owned_launch_ids = [
            launch_id for launch_id, launch in self._launches.items() if launch.owner_id == owner_id
        ]
        for launch_id in owned_launch_ids:
            del self._launches[launch_id]

    def _forget_old_launches(self, owner_id: UUID) -> None:
        owned_launches = [
            launch for launch in self._launches.values() if launch.owner_id == owner_id
        ]
        excess_count = len(owned_launches) - MAX_LAUNCHES_PER_OWNER + 1
        if excess_count <= 0:
            return
        finished_oldest_first = sorted(
            (launch for launch in owned_launches if not launch.is_running),
            key=lambda launch: launch.started_at,
        )
        for launch in finished_oldest_first[:excess_count]:
            del self._launches[launch.launch_id]


def _require_scenario(scenario_id: str) -> DemoScenario:
    scenario = SCENARIOS_BY_ID.get(scenario_id)
    if scenario is None:
        raise DemoScenarioMissingError
    return scenario
