from typing import TYPE_CHECKING
from uuid import UUID

from contracts.auth import CurrentUser, TokenResponse
from contracts.demo import DemoCatalogView, DemoLaunchView, DemoResetResult, DemoStatusView

if TYPE_CHECKING:
    from modules.demo.service import DemoService


class DemoClient:
    def __init__(self, service: "DemoService") -> None:
        self._service = service

    def status(self) -> DemoStatusView:
        return self._service.status()

    async def login(self) -> TokenResponse:
        return await self._service.login()

    async def ensure_demo_account(self) -> CurrentUser:
        return await self._service.ensure_demo_account()

    def catalog(self) -> DemoCatalogView:
        return self._service.catalog()

    def launch(self, owner: CurrentUser, scenario_id: str) -> DemoLaunchView:
        return self._service.launch(owner, scenario_id)

    def get_launch(self, owner: CurrentUser, launch_id: UUID) -> DemoLaunchView:
        return self._service.get_launch(owner, launch_id)

    async def reset(self, owner: CurrentUser) -> DemoResetResult:
        return await self._service.reset(owner)

    async def scenario_kit(self, scenario_id: str) -> bytes:
        return await self._service.scenario_kit(scenario_id)

    async def full_kit(self) -> bytes:
        return await self._service.full_kit()

    async def shutdown(self) -> None:
        await self._service.shutdown()
