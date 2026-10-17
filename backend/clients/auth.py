from typing import TYPE_CHECKING

from contracts.auth import CurrentUser, LoginRequest, RegisterRequest, TokenResponse

if TYPE_CHECKING:
    from modules.auth.service import AuthService


class AuthClient:
    def __init__(self, service: "AuthService") -> None:
        self._service = service

    async def register(self, request: RegisterRequest) -> TokenResponse:
        return await self._service.register(request)

    async def login(self, request: LoginRequest) -> TokenResponse:
        return await self._service.login(request)

    async def user_from_token(self, token: str) -> CurrentUser:
        return await self._service.user_from_token(token)
