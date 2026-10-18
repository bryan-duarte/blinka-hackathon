from typing import Literal, Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class JwtSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BLINKA_JWT__", env_file=".env", extra="ignore", frozen=True
    )

    secret: SecretStr
    algorithm: str = "HS256"
    expire_minutes: int = 60


class LlmSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BLINKA_LLM__", env_file=".env", extra="ignore", frozen=True
    )

    base_url: str = "https://openrouter.ai/api"
    api_key: SecretStr = Field(validation_alias="OPENROUTER_API_KEY", default=SecretStr(""))
    model: str = "anthropic/claude-haiku-5.5"
    main_model: str | None = None
    payments_model: str | None = None
    max_tokens: int = 8192
    timeout_s: float = 120
    max_retries: int = 2


class StorageSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BLINKA_STORAGE__", env_file=".env", extra="ignore", frozen=True
    )

    bucket: str = "blinka-evidence"
    region: str = "us-east-1"
    aws_profile: str | None = "panoptico"
    malware_scan_enabled: bool = True
    scan_timeout_seconds: float = 60
    scan_poll_interval_seconds: float = 2


class TextractSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BLINKA_TEXTRACT__", env_file=".env", extra="ignore", frozen=True
    )

    aws_profile: str | None = "panoptico"
    region: str = "us-east-1"


class GuardrailsSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BLINKA_GUARDRAILS__", env_file=".env", extra="ignore", frozen=True
    )

    enforce: bool = False
    guardrail_id: str = ""
    guardrail_version: str = "DRAFT"
    aws_profile: str | None = None
    aws_region: str = "us-east-1"

    @model_validator(mode="after")
    def _require_guardrail_id_when_enforced(self) -> Self:
        if self.enforce and not self.guardrail_id:
            raise ValueError(
                "BLINKA_GUARDRAILS__GUARDRAIL_ID must be set when "
                "BLINKA_GUARDRAILS__ENFORCE is true"
            )
        return self


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


class KapsoSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BLINKA_KAPSO__", env_file=".env", extra="ignore", frozen=True
    )

    api_key: SecretStr = Field(validation_alias="KAPSO_API_KEY", default=SecretStr(""))
    webhook_secret: SecretStr = Field(
        validation_alias="KAPSO_WEBHOOK_SECRET", default=SecretStr("")
    )
    base_url: str = "https://api.kapso.ai"
    webhook_url: str = ""
    callback_url: str = "http://localhost:3000/inbox/whatsapp/callback"
    sandbox_phone_number_id: str = ""
    sandbox_display_number: str = ""


class RealtimeSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BLINKA_REALTIME__", env_file=".env", extra="ignore", frozen=True
    )

    enabled: bool = False
    http_domain: str = ""
    region: str = "us-east-1"
    aws_profile: str | None = "panoptico"
    namespace: str = "inbox"
    thinking_flush_ms: int = 400


class CorsSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BLINKA_CORS__", env_file=".env", extra="ignore", frozen=True
    )

    allow_origins: list[str] = ["http://localhost:3000"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BLINKA_", env_file=".env", extra="ignore", frozen=True
    )

    product_database_url: str
    payments_database_url: str
    jwt: JwtSettings = Field(default_factory=JwtSettings)
    llm: LlmSettings = Field(default_factory=LlmSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    textract: TextractSettings = Field(default_factory=TextractSettings)
    guardrails: GuardrailsSettings = Field(default_factory=GuardrailsSettings)
    composio: ComposioSettings = Field(default_factory=ComposioSettings)
    kapso: KapsoSettings = Field(default_factory=KapsoSettings)
    realtime: RealtimeSettings = Field(default_factory=RealtimeSettings)
    log_format: Literal["console", "json"] = "console"
