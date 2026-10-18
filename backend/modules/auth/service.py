from uuid import UUID

from contracts.auth import CurrentUser, LoginRequest, RegisterRequest, TokenResponse
from core.config import JwtSettings
from core.logging_config import get_logger
from modules.auth import security
from modules.auth.errors import (
    EmailTakenError,
    InvalidCredentialsError,
    InvalidTokenError,
    UserMissingError,
)
from modules.auth.repository import UsersRepository

logger = get_logger(__name__)


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

    async def ensure_user_with_password(self, email: str, password: str) -> CurrentUser:
        normalized_email = email.lower()
        existing = await self._repository.get_by_email(normalized_email)
        if existing is not None:
            if not security.verify_password(password, existing.password_hash):
                await self._repository.set_password_hash(
                    existing.user_id, security.hash_password(password)
                )
                logger.warning("user_password_synced", user_id=existing.user_id)
            return CurrentUser(user_id=existing.user_id, email=existing.email)
        try:
            user_id = await self._repository.insert(
                normalized_email, security.hash_password(password)
            )
        except EmailTakenError:
            concurrent_user = await self._repository.get_by_email(normalized_email)
            if concurrent_user is None:
                raise
            user_id = concurrent_user.user_id
        return CurrentUser(user_id=user_id, email=normalized_email)

    def _issue_token(self, user_id: UUID) -> TokenResponse:
        access_token = security.encode_token(user_id, self._jwt_settings)
        return TokenResponse(access_token=access_token)
