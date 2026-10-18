# Demo Access Lockdown Implementation

## Overview

Remove every credential-free way in: the public demo login, the public demo status and self-registration. While demo mode is on, only `settings.demo.email` can authenticate. The password is owned by the operator in SSM.

## Files to Modify/Create

**Backend**
- `backend/api/routers/demo.py`: delete `demo_public_router` and its `GET /demo/status` and `POST /demo/login` handlers (lines 12-23). Keep the authed `demo_router`.
- `backend/api/routers/__init__.py`: delete the `demo_public_router` import and `include_router` (line 25).
- `backend/modules/demo/service.py`:
  - Delete `status()` (lines 94-96) and `login()` (lines 98-106).
  - Delete imports that become unused (`LoginRequest`, `TokenResponse`, `DemoStatusView`).
- `backend/clients/demo.py`: delete `login` (lines 18-19) and `status`.
- `backend/contracts/demo.py`: delete `DemoStatusView` (lines 85-87). Remove it from `__all__` / exports if listed.
- `backend/api/routers/auth.py`: delete `POST /auth/register` (lines 9-11).
- `backend/modules/auth/service.py`:
  - Delete `register()` (line 23).
  - Add `allowed_email: str | None` to `__init__`.
  - Enforce it in `login()` and `user_from_token()`.
- `backend/clients/auth.py`: delete `register`.
- `backend/contracts/auth.py`: delete `RegisterRequest` if nothing else uses it.
- `backend/container.py`: pass `allowed_email=settings.demo.email if settings.demo.enabled else None` to `AuthService(...)`.
- `backend/api/app.py`: remove `DOMAIN_ERROR_RESPONSES` / handler entries that only served register (`EmailTakenError` → 409). Keep it if `ensure_user_with_password` still references the error, since that is internal.
- `backend/.env.example:70-72`: replace the "public token for the fictional demo data" comment with "Only this account can log in while demo mode is enabled; set the password in SSM".

**Frontend**
- `frontend/src/app/login/page.tsx`:
  - Delete `DemoEntry` (lines 239-292) and its render (line 167).
  - Delete the register mode: the mode state and toggle (lines 10-35, 76-78, 91, 153-165) and `?mode=register` parsing.
  - Drop imports that become unused (`useEffect` at line 5 if unused).
- `frontend/src/lib/api.ts`: delete `register` (lines 182-183), `demoStatus` and `demoLogin` (lines 241-242).
- `frontend/src/lib/types.ts`: delete `DemoStatusView` (lines 439-442) and `RegisterRequest` if present.
- `frontend/src/app/page.tsx`: lines 4, 109-111, 125-127 and 211-213 change `href="/login?mode=register"` to `href="/login"`, with CTA copy "Sign in". Follow `frontend/DESIGN.md`.

**Infra**
- `infra/ssm.tf`:
  - Delete `random_password.demo_password` (lines 6-9).
  - Move `BLINKA_DEMO__PASSWORD` from `managed_params` (line 29) to `operator_params` with `value = local.unassigned_placeholder`, `secure = true`.
  - Add a `moved` block so the existing parameter keeps its value.
- `infra/outputs.tf`: delete `output "demo_password"` (lines 79-83).

## Implementation Guidelines

```python
# backend/modules/auth/service.py (orientative)
class AuthService:
    def __init__(self, repository, jwt_settings, allowed_email: str | None = None) -> None:
        ...
        self._allowed_email = allowed_email.casefold() if allowed_email else None

    async def login(self, request: LoginRequest) -> TokenResponse:
        email = request.email.lower()
        if not self._is_allowed(email):
            raise InvalidCredentialsError          # same error as a bad password: no enumeration
        ...

    async def user_from_token(self, token: str) -> CurrentUser:
        ...
        if not self._is_allowed(user.email):
            raise InvalidTokenError                # → 401, frontend clears token
        return CurrentUser(...)

    def _is_allowed(self, email: str) -> bool:
        return self._allowed_email is None or email.casefold() == self._allowed_email
```

- `ensure_user_with_password` and `get_user` are internal (used by startup and the workers) and are **not** filtered.
- `require_demo_user` (`api/deps.py:48-56`) stays as defense in depth.

```hcl
# infra/ssm.tf (orientative)
moved {
  from = aws_ssm_parameter.managed["BLINKA_DEMO__PASSWORD"]
  to   = aws_ssm_parameter.operator["BLINKA_DEMO__PASSWORD"]
}
```

**Operator steps after the apply** (to go in the implementation PR description, not the code):

```bash
aws ssm put-parameter --profile panoptico --region us-east-1 \
  --name /blinka/prod/BLINKA_DEMO__PASSWORD --type SecureString --overwrite --value '<password>'
./infra/deploy.sh --restart   # ensure_user_with_password re-hashes on boot
```

Constraint: the password must be at least 8 characters and at most 72 bytes (bcrypt).

## Dependencies

None. Module 02's operator checklist depends on this being deployed.

## Integration Notes

- **Login:** the frontend login page posts to `POST /auth/login` (unchanged contract: `{email, password}` → `TokenResponse`).
- **Expired or foreign tokens:** a 401 from any endpoint already clears `blinka_token` and redirects (`lib/api.ts:87-104`).
- **Demo panel:** `inbox/page.tsx:165-168` still calls `api.demoCatalog()`. It now always succeeds, because the only user is the demo user.
