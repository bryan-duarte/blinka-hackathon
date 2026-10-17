from typing import Annotated

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from container import Clients
from contracts.auth import CurrentUser
from core.config import Settings
from modules.auth.errors import InvalidTokenError

_bearer_scheme = HTTPBearer(auto_error=False)


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_clients(request: Request) -> Clients:
    return request.app.state.clients


SettingsDep = Annotated[Settings, Depends(get_settings)]
ClientsDep = Annotated[Clients, Depends(get_clients)]
BearerCredentialsDep = Annotated[HTTPAuthorizationCredentials | None, Security(_bearer_scheme)]


async def get_current_user(clients: ClientsDep, credentials: BearerCredentialsDep) -> CurrentUser:
    if credentials is None:
        raise _unauthorized("missing bearer token")
    try:
        return await clients.auth.user_from_token(credentials.credentials)
    except InvalidTokenError:
        raise _unauthorized("invalid token") from None


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]
