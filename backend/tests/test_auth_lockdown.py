from uuid import UUID, uuid4

import pytest
from pydantic import SecretStr

from contracts.auth import LoginRequest, UserCredentials
from core.config import JwtSettings
from modules.auth import security
from modules.auth.errors import InvalidCredentialsError, InvalidTokenError
from modules.auth.service import AuthService

DEMO_EMAIL = "demo@blinka.dev"
OTHER_EMAIL = "evaluator@example.com"
PASSWORD = "correct horse battery"
JWT_SETTINGS = JwtSettings(secret=SecretStr("test-secret-long-enough-for-hmac-sha256"))
LOW_BCRYPT_COST = 4


class InMemoryUsers:
    def __init__(self, *emails: str) -> None:
        password_hash = security.bcrypt.hashpw(
            PASSWORD.encode(), security.bcrypt.gensalt(rounds=LOW_BCRYPT_COST)
        ).decode()
        self.users = {
            email: UserCredentials(user_id=uuid4(), email=email, password_hash=password_hash)
            for email in emails
        }

    async def get_by_email(self, email: str) -> UserCredentials | None:
        return self.users.get(email)

    async def get_by_id(self, user_id: UUID) -> UserCredentials | None:
        return next((user for user in self.users.values() if user.user_id == user_id), None)


def _locked_service(users: InMemoryUsers) -> AuthService:
    return AuthService(users, JWT_SETTINGS, allowed_email=DEMO_EMAIL)


async def test_demo_account_can_log_in_while_locked():
    locked_service = _locked_service(InMemoryUsers(DEMO_EMAIL))

    token = await locked_service.login(LoginRequest(email=DEMO_EMAIL, password=PASSWORD))

    current_user = await locked_service.user_from_token(token.access_token)
    assert current_user.email == DEMO_EMAIL


async def test_other_accounts_get_the_same_error_as_a_wrong_password():
    users = InMemoryUsers(DEMO_EMAIL, OTHER_EMAIL)

    with pytest.raises(InvalidCredentialsError):
        await _locked_service(users).login(LoginRequest(email=OTHER_EMAIL, password=PASSWORD))


async def test_tokens_issued_to_other_accounts_are_rejected_while_locked():
    users = InMemoryUsers(DEMO_EMAIL, OTHER_EMAIL)
    other_user_id = users.users[OTHER_EMAIL].user_id
    other_token = security.encode_token(other_user_id, JWT_SETTINGS)

    with pytest.raises(InvalidTokenError):
        await _locked_service(users).user_from_token(other_token)


async def test_any_account_can_log_in_when_demo_mode_is_off():
    users = InMemoryUsers(OTHER_EMAIL)
    open_service = AuthService(users, JWT_SETTINGS)

    token = await open_service.login(LoginRequest(email=OTHER_EMAIL, password=PASSWORD))

    assert token.access_token
