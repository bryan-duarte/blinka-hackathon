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

    model: str = "global.anthropic.claude-haiku-5-5"
    main_model: str | None = None
    payments_model: str | None = None
    aws_profile: str | None = None
    aws_region: str = "us-east-1"
    max_tokens: int = 8192
    timeout_s: float = Field(default=120, gt=0)
    connect_timeout_s: float = Field(default=5, gt=0)
    max_retries: int = Field(default=2, ge=0)


class AgentSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BLINKA_AGENT__", env_file=".env", extra="ignore", frozen=True
    )

    run_timeout_s: float = Field(default=300, gt=0)
    max_tool_calls: int = Field(default=30, ge=1)
    max_model_calls: int = Field(default=35, ge=1)


class MemorySettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BLINKA_MEMORY__", env_file=".env", extra="ignore", frozen=True
    )

    enabled: bool = True
    embedding_model: str = "amazon.titan-embed-text-v2:0"
    embedding_dims: int = Field(default=1024, ge=1)
    recall_limit: int = Field(default=5, ge=1, le=20)
    manager_query_limit: int = Field(default=10, ge=1)
    aws_profile: str | None = None
    aws_region: str = "us-east-1"


class StorageSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BLINKA_STORAGE__", env_file=".env", extra="ignore", frozen=True
    )

    bucket: str = "blinka-evidence"
    region: str = "us-east-1"
    aws_profile: str | None = None
    malware_scan_enabled: bool = True
    scan_timeout_seconds: float = 60
    scan_poll_interval_seconds: float = 2


class TextractSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BLINKA_TEXTRACT__", env_file=".env", extra="ignore", frozen=True
    )

    aws_profile: str | None = None
    region: str = "us-east-1"


class GuardrailsSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BLINKA_GUARDRAILS__", env_file=".env", extra="ignore", frozen=True
    )

    enforce: bool = True
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
    aws_profile: str | None = None
    namespace: str = "inbox"
    thinking_flush_ms: int = 400


class FxSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BLINKA_FX__", env_file=".env", extra="ignore", frozen=True
    )

    latest_url: str = "https://open.er-api.com/v6/latest/USD"
    timeout_seconds: float = 2.0
    max_stale_days: int = 7
    live_enabled: bool = True


class DemoSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BLINKA_DEMO__", env_file=".env", extra="ignore", frozen=True
    )

    enabled: bool = False
    email: str = "demo@blinka.dev"
    password: SecretStr | None = None
    company_name: str = "Andescape Labs, Inc."
    inbox_address: str | None = None
    max_running_launches: int = 20

    @model_validator(mode="after")
    def _require_password_when_enabled(self) -> Self:
        if self.enabled and self.password is None:
            raise ValueError("BLINKA_DEMO__PASSWORD is required when demo mode is enabled")
        return self


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BLINKA_WORKERS__", env_file=".env", extra="ignore", frozen=True
    )

    agent_run_concurrency: int = Field(default=8, ge=1)
    inbox_concurrency: int = Field(default=8, ge=1)
    poll_interval_seconds: float = Field(default=15.0, gt=0)
    db_pool_size: int = Field(default=10, ge=1)
    db_max_overflow: int = Field(default=10, ge=0)
    checkpointer_pool_size: int = Field(default=10, ge=1)
    blocking_io_threads: int = Field(default=64, ge=1)


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
    agent_database_url: str
    jwt: JwtSettings = Field(default_factory=JwtSettings)
    llm: LlmSettings = Field(default_factory=LlmSettings)
    agent: AgentSettings = Field(default_factory=AgentSettings)
    memory: MemorySettings = Field(default_factory=MemorySettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    textract: TextractSettings = Field(default_factory=TextractSettings)
    guardrails: GuardrailsSettings = Field(default_factory=GuardrailsSettings)
    composio: ComposioSettings = Field(default_factory=ComposioSettings)
    kapso: KapsoSettings = Field(default_factory=KapsoSettings)
    realtime: RealtimeSettings = Field(default_factory=RealtimeSettings)
    fx: FxSettings = Field(default_factory=FxSettings)
    demo: DemoSettings = Field(default_factory=DemoSettings)
    workers: WorkerSettings = Field(default_factory=WorkerSettings)
    log_format: Literal["console", "json"] = "console"
