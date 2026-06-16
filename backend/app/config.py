from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "AgentHub Backend"
    app_env: str = "development"
    app_version: str = "0.1.0"
    api_v1_prefix: str = "/api/v1"
    cors_allow_origins: list[str] = ["*"]

    agentscope_provider: str = "dashscope"
    agentscope_model: str = "qwen3.6-plus"
    agentscope_mount_path: str = "/agentscope"

    openai_api_key: SecretStr | None = None
    openai_base_url: str | None = None
    dashscope_api_key: SecretStr | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
