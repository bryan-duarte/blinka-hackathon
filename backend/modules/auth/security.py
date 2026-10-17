from datetime import UTC, datetime, timedelta
from uuid import UUID

import bcrypt
import jwt

from core.config import JwtSettings
from modules.auth.errors import InvalidTokenError

BCRYPT_COST = 12


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=BCRYPT_COST)).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def encode_token(user_id: UUID, jwt_settings: JwtSettings) -> str:
    expires_at = datetime.now(UTC) + timedelta(minutes=jwt_settings.expire_minutes)
    payload = {"sub": str(user_id), "exp": expires_at}
    return jwt.encode(
        payload, jwt_settings.secret.get_secret_value(), algorithm=jwt_settings.algorithm
    )


def decode_token(token: str, jwt_settings: JwtSettings) -> UUID:
    try:
        payload = jwt.decode(
            token, jwt_settings.secret.get_secret_value(), algorithms=[jwt_settings.algorithm]
        )
    except jwt.PyJWTError as error:
        raise InvalidTokenError from error
    return UUID(payload["sub"])
