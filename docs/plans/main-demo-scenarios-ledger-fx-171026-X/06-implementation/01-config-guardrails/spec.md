# Config & Secure-by-default Guardrail Implementation

## Overview

Add the `FxSettings` and `DemoSettings` groups, turn on guardrail enforcement by default (it fails fast without an ID), and fix the misspelled env key.

## Files to Modify/Create

- `backend/core/config.py`:
  - `GuardrailsSettings.enforce` default changes from `False` to `True`.
  - New `FxSettings` and `DemoSettings` classes.
  - Expose both on `Settings` the same way the existing groups are exposed. Check how `Settings.guardrails` is built (property vs. `Field(default_factory=...)`) and mirror it.
- `backend/.env`: rename `BLINKA_GUARDRAILS_ENFORCE` to `BLINKA_GUARDRAILS__ENFORCE`, and remove the dead `BLINKA_AGENT_DATABASE_URL`. Add `BLINKA_DEMO__ENABLED=true`, `BLINKA_DEMO__PASSWORD=<local value>` and `BLINKA_FX__LIVE_ENABLED=true`.
- `backend/.env.example`:
  - Document `BLINKA_GUARDRAILS__ENFORCE`: it defaults to true, and only `false` disables it.
  - Document that `BLINKA_GUARDRAILS__GUARDRAIL_ID` is required unless enforcement is disabled.
  - Add the `BLINKA_FX__*` and `BLINKA_DEMO__*` keys with their defaults.
- `backend/api/app.py` `lifespan`: keep `logger.info("guardrails_configured", enforce=...)`, and also log `demo_mode_configured` with `enabled` and `email`.

## Implementation Guidelines

The snippets below are orientative.

```python
class GuardrailsSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BLINKA_GUARDRAILS__", env_file=".env", extra="ignore", frozen=True)
    enforce: bool = True
    ...  # keep _require_guardrail_id_when_enforced as is


class FxSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BLINKA_FX__", env_file=".env", extra="ignore", frozen=True)
    latest_url: str = "https://open.er-api.com/v6/latest/USD"
    timeout_seconds: float = 2.0
    max_stale_days: int = 7
    live_enabled: bool = True


class DemoSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BLINKA_DEMO__", env_file=".env", extra="ignore", frozen=True)
    enabled: bool = False
    email: str = "demo@blinka.dev"
    password: SecretStr | None = None
    company_name: str = "Andescape Labs, Inc."
    inbox_address: str | None = None   # Gmail/Outlook address connected to the demo account, shown in the self-send kit

    @model_validator(mode="after")
    def _require_password_when_enabled(self) -> Self:
        if self.enabled and self.password is None:
            raise ValueError("BLINKA_DEMO__PASSWORD is required when demo mode is enabled")
        return self
```

- Name the FX flag field `live_enabled` and keep the plain prefix. Use the `is_` prefix only for local variables. The `is_live_enabled` alias shown in 03-design can be dropped. Follow the existing `enabled` naming in `RealtimeSettings`.
- Existing tests that build `Settings()` or `GuardrailsSettings()` without an ID now fail validation. Pass `enforce=False` explicitly wherever tests build these settings. That is a mechanical fix, not new tests.

## Dependencies

None.

## Integration Notes

- `settings.fx` is consumed by 02-fx-conversion (`FxService`, `OpenErApiProvider`).
- `settings.demo` is consumed by 04-demo-seed, 08-demo-api and `lifespan`.
- `settings.guardrails.enforce` and `settings.storage.malware_scan_enabled` feed `DemoCatalogView.is_guardrail_enforced` and `is_malware_scan_enabled` in 05-demo-scenarios.
