from uuid import UUID

from pydantic import EmailStr

from contracts._base import ApiModel, StrictModel


class UserCredentials(StrictModel):
    user_id: UUID
    email: str
    password_hash: str


class LoginRequest(ApiModel):
    email: EmailStr
    password: str


class TokenResponse(ApiModel):
    access_token: str
    token_type: str = "bearer"


class CurrentUser(ApiModel):
    user_id: UUID
    email: str
