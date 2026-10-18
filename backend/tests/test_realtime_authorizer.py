import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import jwt
import pytest
from pydantic import SecretStr

from core.config import JwtSettings
from modules.auth.security import encode_token

AUTHORIZER_PATH = (
    Path(__file__).resolve().parents[2] / "infra" / "lambda" / "realtime_authorizer" / "handler.py"
)
JWT_SECRET = "test-realtime-secret-with-32-bytes!"
MAX_CACHE_SECONDS = 300


def _load_authorizer():
    spec = importlib.util.spec_from_file_location("realtime_authorizer", AUTHORIZER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


authorizer = _load_authorizer()


@pytest.fixture(autouse=True)
def _jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)


def _login_token(user_id: str) -> str:
    settings = JwtSettings(secret=SecretStr(JWT_SECRET))
    return encode_token(user_id, settings)


def _event(token: str, operation: str, channel: str | None = None) -> dict:
    return {
        "authorizationToken": token,
        "requestContext": {"operation": operation, "channel": channel},
    }


def test_connect_is_allowed_with_a_valid_login_token() -> None:
    user_id = str(uuid4())
    response = authorizer.handler(_event(_login_token(user_id), "EVENT_CONNECT"), None)
    assert response["isAuthorized"] is True
    assert response["handlerContext"] == {"sub": user_id}
    assert 0 < response["ttlOverride"] <= MAX_CACHE_SECONDS


def test_subscribe_is_allowed_only_on_the_users_own_inbox() -> None:
    user_id = str(uuid4())
    token = _login_token(user_id)
    own = authorizer.handler(_event(token, "EVENT_SUBSCRIBE", f"/inbox/{user_id}"), None)
    other = authorizer.handler(_event(token, "EVENT_SUBSCRIBE", f"/inbox/{uuid4()}"), None)
    assert own["isAuthorized"] is True
    assert other == authorizer.DENIED


@pytest.mark.parametrize("channel", ["/inbox/*", "/*", "/inbox", None])
def test_wildcard_and_partial_channels_are_denied(channel: str | None) -> None:
    token = _login_token(str(uuid4()))
    assert authorizer.handler(_event(token, "EVENT_SUBSCRIBE", channel), None) == authorizer.DENIED


def test_publish_is_never_authorized_for_browser_tokens() -> None:
    user_id = str(uuid4())
    event = _event(_login_token(user_id), "EVENT_PUBLISH", f"/inbox/{user_id}")
    assert authorizer.handler(event, None) == authorizer.DENIED


def test_tampered_expired_and_unsigned_tokens_are_denied() -> None:
    user_id = str(uuid4())
    expired = jwt.encode(
        {"sub": user_id, "exp": datetime.now(UTC) - timedelta(minutes=1)}, JWT_SECRET, "HS256"
    )
    wrong_secret = jwt.encode(
        {"sub": user_id, "exp": datetime.now(UTC) + timedelta(minutes=5)},
        "another-secret-with-at-least-32-bytes",
        "HS256",
    )
    unsigned = jwt.encode(
        {"sub": user_id, "exp": datetime.now(UTC) + timedelta(minutes=5)}, None, "none"
    )
    for token in (expired, wrong_secret, unsigned, "not-a-jwt", ""):
        assert authorizer.handler(_event(token, "EVENT_CONNECT"), None) == authorizer.DENIED
