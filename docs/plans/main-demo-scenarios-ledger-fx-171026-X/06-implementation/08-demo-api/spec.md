# Demo API, Account Bootstrap & Wiring Implementation

## Overview

This module adds the HTTP surface for the demo (status, login shortcut, catalog, launch, launch status, reset, kit downloads). It also ensures the demo account exists on startup and wires `DemoService` into the container and lifespan.

## Files to Modify/Create

- `backend/api/routers/demo.py` (new): two routers.
  - `demo_public_router = APIRouter(prefix="/demo", tags=["demo"])`, with no auth:
    - `GET /demo/status` → `DemoStatusView`
    - `POST /demo/login` → `TokenResponse`. Returns 404 `DemoDisabledError` when demo mode is disabled.
  - `demo_router = APIRouter(prefix="/demo", tags=["demo"])`, with auth plus `DemoUserDep`:
    - `GET /demo/scenarios` → `DemoCatalogView`
    - `POST /demo/scenarios/{scenario_id}/launch` (202) → `DemoLaunchView`
    - `GET /demo/launches/{launch_id}` → `DemoLaunchView`
    - `POST /demo/reset` → `DemoResetResult`
    - `GET /demo/kit` → `Response(content=zip, media_type="application/zip", headers={"Content-Disposition": 'attachment; filename="andescape-demo-kit.zip"'})`
    - `GET /demo/scenarios/{scenario_id}/kit` → same shape, with `filename="{scenario_id}.zip"`
- `backend/api/routers/__init__.py`: include `demo_public_router` without dependencies and `demo_router` with `dependencies=[Depends(get_current_user)]`.
- `backend/api/deps.py`: add `require_demo_user(user: CurrentUserDep, settings: SettingsDep) -> CurrentUser`. It raises `DemoDisabledError` when `not settings.demo.enabled`, and `DemoAccessDeniedError` when `user.email.casefold() != settings.demo.email.casefold()`. Expose it as `DemoUserDep = Annotated[CurrentUser, Depends(require_demo_user)]`.
- `backend/api/app.py`:
  - Add these entries to `DOMAIN_ERROR_RESPONSES`:

    | Error | Status | Detail |
    |---|---|---|
    | `DemoDisabledError` | 404 | "demo mode is disabled" |
    | `DemoAccessDeniedError` | 403 | "only the demo account can do this" |
    | `DemoScenarioMissingError` | 404 | "demo scenario not found" |
    | `DemoLaunchMissingError` | 404 | "demo launch not found" |
    | `DemoBusyError` | 409 | "demo is resetting, try again" |
    | `DemoResetFailedError` | 500 | "demo reset failed" |
    | `TrustedForwarderMissingError` (07) | 404 | — |

  - In `lifespan`, after the recovery calls: `if settings.demo.enabled: await clients.demo.ensure_demo_account()`.
  - In `finally`, call `await clients.demo.shutdown()` before `inbox.shutdown()`.
- `backend/clients/demo.py` (new): `DemoClient`, a thin facade over every `DemoService` public method.
- `backend/container.py`: build `DemoService` after inbox and payments, add `Clients.demo`, and add `Clients.accountability` (09).
- `backend/modules/demo/service.py`: add `ensure_demo_account()`, `login()` and `status()`.

## Implementation Guidelines

The examples below are orientative.

```python
class DemoService:
    def __init__(
        self,
        settings: DemoSettings,
        auth: AuthClient,
        policy: PaymentPolicyClient,
        inbox: InboxClient,
        payments: PaymentsClient,
        files: FilesClient,
        realtime: RealtimeClient,
        seeder: DemoSeeder,
        reset_repository: DemoResetRepository,
        registry: ExecutionRegistry,
        destinations: KitDestinations,
        guardrail_enforced: bool,
        malware_scan_enabled: bool,
    ) -> None: ...

    async def ensure_demo_account(self) -> CurrentUser:
        owner = await self._auth.ensure_user(self._settings.email, self._settings.password.get_secret_value())
        try:
            await self._policy.get_policy(owner)
        except PolicyMissingError:
            seeded_bills = await self._seeder.seed(owner)
            logger.info("demo_account_seeded", owner_id=owner.user_id, seeded_bills=seeded_bills)
        return owner

    async def login(self) -> TokenResponse:
        if not self._settings.enabled:
            raise DemoDisabledError
        return await self._auth.login(LoginRequest(email=self._settings.email, password=self._settings.password.get_secret_value()))
```

- `AuthService.ensure_user(email, password) -> CurrentUser` is a new method (with a mirror in `AuthClient`). It returns the existing user when one exists; otherwise it registers a new one. On an existing user it does not reset the password.
- `ensure_demo_account` must be safe to call concurrently: two workers can start at the same time. Catch `EmailTakenError` on register and re-read the user.
- Security: `/demo/login` hands a token to anyone, which is intended for a public hackathon demo. That only happens when `BLINKA_DEMO__ENABLED=true`, and the setting defaults to `false`. Log `demo_login_issued` on each call.

## Dependencies

- 05, 06 and 07 (`DemoService` methods), 01 (`DemoSettings`), `AuthClient`.

## Integration Notes

- The frontend `api.ts` (10) adds these calls:
  - `demoStatus()`, `demoLogin()`, `demoCatalog()`
  - `launchScenario(id)`, `demoLaunch(id)`, `resetDemo()`
  - `downloadDemoKit()`, `downloadScenarioKit(id)`: blob fetches with the Bearer token, saved through a temporary object URL
  - `trustedForwarders()`, `addTrustedForwarder()`, `deleteTrustedForwarder()`
- The login page calls `demoStatus()` on mount and shows the button only when `is_enabled` is true.
