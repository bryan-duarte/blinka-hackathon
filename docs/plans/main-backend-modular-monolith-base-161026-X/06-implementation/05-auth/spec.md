# Auth Module

## Overview

JWT access-token auth: register/login, bcrypt hashing, `get_current_user` dependency protecting every route except `/health` and `/auth/*`.

## Files to Create

- `backend/modules/auth/__init__.py` — facade: exports `AuthService`, `EmailTakenError`, `InvalidCredentialsError`
- `backend/modules/auth/errors.py`:

```python
class AuthError(Exception): ...
class EmailTakenError(AuthError): ...        # -> 409
class InvalidCredentialsError(AuthError): ... # -> 401
class InvalidTokenError(AuthError): ...       # -> 401 (raised by token decode)
```

- `backend/modules/auth/models.py` — `User(ProductBase)` per 03-design.md (id, email unique+indexed lowercase, password_hash, created_at).
- `backend/modules/auth/repository.py` — `UsersRepository(sessionmaker: async_sessionmaker[AsyncSession])`, queries via SQLAlchemy 2.0 `select()`:
  - `async insert(email, password_hash) -> uuid.UUID` (unique-violation → caller maps to `EmailTakenError`)
  - `async get_by_email(email) -> User | None` (returns the ORM entity)
- `backend/modules/auth/security.py` — `hash_password`, `verify_password` (bcrypt, cost 12), `encode_token(user_id)`, `decode_token(token) -> uuid.UUID` (pyjwt HS256, `exp` from settings; any jwt error → `InvalidTokenError`).
- `backend/modules/auth/service.py`:

```python
class AuthService:
    def __init__(self, repo: UsersRepository, jwt_settings: JwtSettings) -> None: ...
    async def register(self, request: RegisterRequest) -> TokenResponse   # 409 if taken
    async def login(self, request: LoginRequest) -> TokenResponse          # 401 on bad creds
    async def user_from_token(self, token: str) -> CurrentUser             # contract in contracts/auth.py
```

- `backend/api/routers/auth.py` — `auth_router = APIRouter(prefix="/auth", tags=["auth"])`:
  - `POST /auth/register` → 201 `TokenResponse`
  - `POST /auth/login` → 200 `TokenResponse`
  - Router-specific deps inline: `_bearer = HTTPBearer(auto_error=False)`, `_credentials_dep`.
- `backend/api/deps.py` — `get_current_user` GLOBAL dependency (needs `AuthService.user_from_token` via container; used by every protected router): 401 with `WWW-Authenticate: Bearer` on failure.
- `backend/clients/auth.py`:

```python
class AuthClient:
    def __init__(self, service: "AuthService") -> None: ...
    async def register(self, request: RegisterRequest) -> TokenResponse: ...
    async def login(self, request: LoginRequest) -> TokenResponse: ...
    async def user_from_token(self, token: str) -> CurrentUser: ...
```

- `contracts/auth.py` — `RegisterRequest`, `LoginRequest`, `TokenResponse`, `CurrentUser(user_id: UUID, email: str)` (ApiModel).

## Implementation Guidelines

- Timing-safe compare comes free via bcrypt.verify; never log passwords or tokens.
- Route handlers use `ClientsDep`; `get_current_user` needs its own `Depends` chain (bearer → service).
- `email` column lookups are case-insensitive: store lowercase, compare lowercase.

## Dependencies

02-backend-skeleton, 04-persistence-alembic (users table).

## Integration Notes

`get_current_user` is attached in `api/routes.py` to every router except health/auth. `CurrentUser.user_id` is the `owner_id` used by `files` and `sessions` modules — the only identity primitive in the system.
