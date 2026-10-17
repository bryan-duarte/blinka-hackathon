from typing import Literal

from pydantic import Field, SecretStr
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

    endpoint_url: str = "http://localhost:9000"
    bucket: str = "blinka-files"
    access_key_id: str = "minioadmin"
    secret_access_key: SecretStr = SecretStr("minioadmin")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BLINKA_", env_file=".env", extra="ignore", frozen=True
    )

    product_database_url: str
    agent_database_url: str
    payments_database_url: str
    jwt: JwtSettings = Field(default_factory=JwtSettings)
    llm: LlmSettings = Field(default_factory=LlmSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    guardrails_enforce: bool = False
    log_format: Literal["console", "json"] = "console"
