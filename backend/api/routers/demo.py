from uuid import UUID

from fastapi import APIRouter, Response, status

from api.deps import ClientsDep, DemoUserDep
from contracts.demo import DemoCatalogView, DemoLaunchView, DemoResetResult

ZIP_MEDIA_TYPE = "application/zip"
FULL_KIT_FILENAME = "andescape-demo-kit.zip"

demo_router = APIRouter(prefix="/demo", tags=["demo"])


@demo_router.get("/scenarios", response_model=DemoCatalogView)
async def get_catalog(user: DemoUserDep, clients: ClientsDep) -> DemoCatalogView:
    return clients.demo.catalog()


@demo_router.post(
    "/scenarios/{scenario_id}/launch",
    response_model=DemoLaunchView,
    status_code=status.HTTP_202_ACCEPTED,
)
async def launch_scenario(
    scenario_id: str, user: DemoUserDep, clients: ClientsDep
) -> DemoLaunchView:
    return clients.demo.launch(user, scenario_id)


@demo_router.get("/launches/{launch_id}", response_model=DemoLaunchView)
async def get_launch(launch_id: UUID, user: DemoUserDep, clients: ClientsDep) -> DemoLaunchView:
    return clients.demo.get_launch(user, launch_id)


@demo_router.post("/reset", response_model=DemoResetResult)
async def reset_demo(user: DemoUserDep, clients: ClientsDep) -> DemoResetResult:
    return await clients.demo.reset(user)


@demo_router.get("/kit")
async def download_full_kit(user: DemoUserDep, clients: ClientsDep) -> Response:
    return _zip_response(await clients.demo.full_kit(), FULL_KIT_FILENAME)


@demo_router.get("/scenarios/{scenario_id}/kit")
async def download_scenario_kit(
    scenario_id: str, user: DemoUserDep, clients: ClientsDep
) -> Response:
    return _zip_response(await clients.demo.scenario_kit(scenario_id), f"{scenario_id}.zip")


def _zip_response(content: bytes, filename: str) -> Response:
    return Response(
        content=content,
        media_type=ZIP_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
