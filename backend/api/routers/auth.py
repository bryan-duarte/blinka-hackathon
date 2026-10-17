from fastapi import APIRouter, status

from api.deps import ClientsDep
from contracts.auth import LoginRequest, RegisterRequest, TokenResponse

auth_router = APIRouter(prefix="/auth", tags=["auth"])


@auth_router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest, clients: ClientsDep) -> TokenResponse:
    return await clients.auth.register(request)


@auth_router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, clients: ClientsDep) -> TokenResponse:
    return await clients.auth.login(request)
