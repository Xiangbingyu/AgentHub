from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AgentHub Python Service"
    app_env: str = "development"
    app_version: str = "0.1.0"
    sqlite_db_path: str = "./.AgentHub/agenthub.db"
    session_workspace_root: str = "./.AgentHub/session-workspaces"
    test_api_key: str | None = None
    test_base_url: str | None = None
    test_model: str | None = None
    test_workspace_path: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
