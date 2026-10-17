from uuid import UUID

from contracts.auth import CurrentUser, LoginRequest, RegisterRequest, TokenResponse
from core.config import JwtSettings
from modules.auth import security
from modules.auth.errors import InvalidCredentialsError, InvalidTokenError, UserMissingError
from modules.auth.repository import UsersRepository


class AuthService:
    def __init__(self, repository: UsersRepository, jwt_settings: JwtSettings) -> None:
        self._repository = repository
        self._jwt_settings = jwt_settings

    async def register(self, request: RegisterRequest) -> TokenResponse:
        email = request.email.lower()
        password_hash = security.hash_password(request.password)
        user_id = await self._repository.insert(email, password_hash)
        return self._issue_token(user_id)

    async def login(self, request: LoginRequest) -> TokenResponse:
        user = await self._repository.get_by_email(request.email.lower())
        if user is None:
            raise InvalidCredentialsError
        if not security.verify_password(request.password, user.password_hash):
            raise InvalidCredentialsError
        return self._issue_token(user.user_id)

    async def user_from_token(self, token: str) -> CurrentUser:
        user_id = security.decode_token(token, self._jwt_settings)
        user = await self._repository.get_by_id(user_id)
        if user is None:
            raise InvalidTokenError
        return CurrentUser(user_id=user.user_id, email=user.email)

    async def get_user(self, user_id: UUID) -> CurrentUser:
        user = await self._repository.get_by_id(user_id)
        if user is None:
            raise UserMissingError
        return CurrentUser(user_id=user.user_id, email=user.email)

    def _issue_token(self, user_id: UUID) -> TokenResponse:
        access_token = security.encode_token(user_id, self._jwt_settings)
        return TokenResponse(access_token=access_token)
