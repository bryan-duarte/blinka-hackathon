# Config & Dependencies Implementation

## Overview

This adds the Composio SDK, new settings groups for guardrails, Composio and CORS, and moves the background task registry into `core`, where both payments and inbox can use it.

## Files to Modify/Create

- `backend/pyproject.toml`: add `composio==0.28.0` and `composio-client==2.0.0rc17`, and move `httpx>=0.28` from `[dependency-groups].dev` to `[project].dependencies`.
- `backend/uv.lock`: regenerate with `uv lock`.
- `backend/core/config.py`: add `GuardrailsSettings`, `ComposioSettings` and `CorsSettings`, add `Settings.guardrails` and `Settings.composio`, and remove `Settings.guardrails_enforce`.
- `backend/.env.example`: add the new keys and remove `BLINKA_GUARDRAILS_ENFORCE`.
- `backend/core/background.py` (new): exports `ExecutionRegistry`.
- `backend/modules/payments/runner.py`: delete the `ExecutionRegistry` class (lines 33-54) and import it from `core.background`. Remove the `functools.partial` and `Coroutine` imports if they become unused.
- `backend/modules/payments/__init__.py`: keep `ExecutionRegistry` in `__all__`, but import it from `core.background`.

## Implementation Guidelines

### Commands

The snippets in this section are orientative.

```bash
cd backend
uv add "composio==0.28.0" "composio-client==2.0.0rc17"   # NEVER --prerelease=allow
uv remove --dev httpx && uv add "httpx>=0.28"
uv lock && uv sync
uv run python -c "import composio, httpx; print(httpx.__version__)"   # expect 0.28.x
```

### `core/config.py`

Follow the existing per-group `BaseSettings` pattern:

```python
class GuardrailsSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BLINKA_GUARDRAILS__", env_file=".env", extra="ignore", frozen=True
    )

    enforce: bool = False
    guardrail_id: str = ""
    guardrail_version: str = "DRAFT"
    aws_profile: str | None = None
    aws_region: str = "us-east-1"


class ComposioSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BLINKA_COMPOSIO__", env_file=".env", extra="ignore", frozen=True
    )

    api_key: SecretStr = Field(validation_alias="COMPOSIO_API_KEY", default=SecretStr(""))
    webhook_secret: SecretStr = Field(
        validation_alias="COMPOSIO_WEBHOOK_SECRET", default=SecretStr("")
    )
    gmail_auth_config_id: str = ""
    outlook_auth_config_id: str = ""
    gmail_toolkit_version: str = "20261015_00"
    outlook_toolkit_version: str = "20261014_00"
    gmail_poll_interval_minutes: int = 15
    callback_url: str = "http://localhost:3000/inbox/callback"


class CorsSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BLINKA_CORS__", env_file=".env", extra="ignore", frozen=True
    )

    allow_origins: list[str] = ["http://localhost:3000"]


class Settings(BaseSettings):
    ...
    guardrails: GuardrailsSettings = Field(default_factory=GuardrailsSettings)
    composio: ComposioSettings = Field(default_factory=ComposioSettings)
    log_format: Literal["console", "json"] = "console"
```

- `CorsSettings` is **not** nested in `Settings`. `create_app()` instantiates it directly, because `Settings()` needs DB URLs and is built in `lifespan`.
- `validation_alias` makes the alias the only accepted env name, so `COMPOSIO_API_KEY` in `backend/.env` works as is.

### `.env.example`

Add these lines, matching the existing section-comment style:

```
# Guardrails (nested group: BLINKA_GUARDRAILS__*)
BLINKA_GUARDRAILS__ENFORCE=true
BLINKA_GUARDRAILS__GUARDRAIL_ID=
BLINKA_GUARDRAILS__GUARDRAIL_VERSION=1
BLINKA_GUARDRAILS__AWS_PROFILE=panoptico
BLINKA_GUARDRAILS__AWS_REGION=us-east-1

# Composio (nested group: BLINKA_COMPOSIO__*)
COMPOSIO_API_KEY=
COMPOSIO_WEBHOOK_SECRET=
BLINKA_COMPOSIO__GMAIL_AUTH_CONFIG_ID=
BLINKA_COMPOSIO__OUTLOOK_AUTH_CONFIG_ID=

# CORS (nested group: BLINKA_CORS__*)
BLINKA_CORS__ALLOW_ORIGINS=["http://localhost:3000"]
```

Do **not** edit `backend/.env`. It holds secrets, so the final report tells the user which lines to add, and that `BLINKA_GUARDRAILS_ENFORCE` must be renamed.

### `core/background.py`

Move the class verbatim from `modules/payments/runner.py:33-54`, with two generic renames: `run_id` becomes `task_id`, and the log event becomes `"background_task_crashed"`.

```python
class ExecutionRegistry:
    def __init__(self) -> None:
        self._tasks: dict[UUID, asyncio.Task[None]] = {}

    def spawn(self, task_id: UUID, execution: Coroutine[object, object, None]) -> None: ...
    def _reap(self, task_id: UUID, task: asyncio.Task[None]) -> None: ...  # logger.error("background_task_crashed", task_id=..., exc_info=...)
    async def shutdown(self) -> None: ...
```

## Dependencies

`composio==0.28.0`, `composio-client==2.0.0rc17` and `httpx>=0.28`.

## Integration Notes

- `container.py` keeps `from modules.payments import ExecutionRegistry`, or it can switch to `core.background`. Either works.
- `settings.guardrails` replaces `settings.guardrails_enforce`, which is used in `container.py:52`. That line is updated in spec 06.
