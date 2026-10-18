from fastapi import APIRouter

from api.deps import ClientsDep
from contracts.auth import LoginRequest, TokenResponse

auth_router = APIRouter(prefix="/auth", tags=["auth"])


@auth_router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, clients: ClientsDep) -> TokenResponse:
    return await clients.auth.login(request)
