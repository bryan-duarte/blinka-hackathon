from typing import TYPE_CHECKING
from uuid import UUID

from contracts.auth import CurrentUser, LoginRequest, TokenResponse

if TYPE_CHECKING:
    from modules.auth.service import AuthService


class AuthClient:
    def __init__(self, service: "AuthService") -> None:
        self._service = service

    async def login(self, request: LoginRequest) -> TokenResponse:
        return await self._service.login(request)

    async def user_from_token(self, token: str) -> CurrentUser:
        return await self._service.user_from_token(token)

    async def get_user(self, user_id: UUID) -> CurrentUser:
        return await self._service.get_user(user_id)

    async def ensure_user_with_password(self, email: str, password: str) -> CurrentUser:
        return await self._service.ensure_user_with_password(email, password)
