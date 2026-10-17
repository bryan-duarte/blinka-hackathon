from fastapi import APIRouter

from api.deps import ClientsDep
from contracts.prompts import HelloWorldReport

diagnostics_router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


@diagnostics_router.post("/hello-world", response_model=HelloWorldReport)
async def hello_world(clients: ClientsDep) -> HelloWorldReport:
    return await clients.orchestrator.hello_world()
