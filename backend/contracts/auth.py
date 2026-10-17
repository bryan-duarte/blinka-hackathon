from uuid import UUID

from pydantic import EmailStr, Field, field_validator

from contracts._base import ApiModel, StrictModel

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_BYTES = 72


class UserCredentials(StrictModel):
    user_id: UUID
    email: str
    password_hash: str


class RegisterRequest(ApiModel):
    email: EmailStr
    password: str = Field(min_length=MIN_PASSWORD_LENGTH)

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, password: str) -> str:
        if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
            raise ValueError(f"password must be at most {MAX_PASSWORD_BYTES} bytes")
        return password


class LoginRequest(ApiModel):
    email: EmailStr
    password: str


class TokenResponse(ApiModel):
    access_token: str
    token_type: str = "bearer"


class CurrentUser(ApiModel):
    user_id: UUID
    email: str
